"""
=============
neutcurve
=============
Module for fitting neutralization curves.
"""


import math

import pandas
import scipy
import scipy.optimize

import dms_tools2.plot


class fourParamLogistic:
    """Fit a 4-parameter logistic neutralization curve.

    Fits :math:`f(c) = b + \\frac{t - b}{1 + (c/m)^s}`
    where :math:`f(c)` is the fraction surviving at
    concentration :math:`c`, :math:`m` is the midpoint
    of the neutralization curve, :math:`t` is the top
    value (e.g., 1), :math:`b` is the bottom value (e.g., 0),
    and :math:`s` is the slope of the curve.

    This documentation is written for the case when 
    :math:`f(c)` is the fraction **surviving**, meaning that
    :math:`f(c)` gets smaller as :math:`c` gets larger.
    This should lead you to fit :math:`s > 0`.
    If you instead use :math:`f(c)` as the fraction neutralized,
    you will fit :math:`s < 1`. In this case, the interpretation
    of `top` and `bottom` will be reversed. However, this class
    has **not** been extensively tested in that scenario, and
    so may not work completely correctly if you have
    :math:`f(c)` represent the fraction neutralized.

    To initialize and fit an object, provide the following:
        `cs` (array-like)
            Concentrations for which we have measurements
            to fit.
        `fs` (array-like)
            Same length as `cs`, with `fs[i]` giving
            fraction surviving at `cs[i]`.
        `fixbottom` (bool)
            If `False`, we fit the bottom value of the
            curve. If you instead want to fix it,
            provide the number to fix it to (typically 0).
            Fix this number if you think that the neutralization
            goes to completion at high enough antibody.
            concentration. For some viruses (such as HIV),
            the neutralization never goes to completion as 
            there are some resistant viruses (such as due
            to glycan heterogeneity) -- if that is the case,
            you want to fit the bottom rather than fix it to 0.
        `fixtop` (`False` or a float)
            If `False`, we fit the top value of the
            curve. If you instead want to fix it,
            provide the number to fix it to (typically 1).
            Usually you do **not** want to fit this value,
            as the fraction surviving should always be one
            at sufficiently low antibody concentration.

    After initialization, you can access the following
    attributes:
        `cs` (numpy array)
            Array of the concentration measurements we have
            fitted, sorted from lowest to highest. 
        `fs` (numpy array)
            Array of the fraction surviving measurements
            corresponding to the entries in `cs`.
        `midpoint` (float)
            Midpoint of curve, :math:`m` in equation above.
        `slope` (float)
            Hill slope of curve, :math:`s` in equation above.
        `bottom` (float)
            Bottom of curve (value as :math:`c` gets large),
            :math:`b` in equation above.
        `top` (float)
            Top of curve (value as :math:`c` get small),
            :math:`t` in equation above.

    You can use the `ic50` function to get the fitted IC50.

    As an example, we first simulate some data with known
    parameter values:

    >>> m = 0.03
    >>> s = 1.9
    >>> b = 0.1
    >>> t = 1.0
    >>> cs = [0.002 * 2**x for x in range(9)]
    >>> fs = [fourParamLogistic.evaluate(c, m, s, b, t) for c in cs]

    Now we fit to these data, and then confirm that the
    fitted values are close to the ones used for the
    simulation:

    >>> neut = fourParamLogistic(cs, fs)
    >>> scipy.allclose(neut.midpoint, m)
    True
    >>> scipy.allclose(neut.slope, s)
    True
    >>> scipy.allclose(neut.top, t)
    True
    >>> scipy.allclose(neut.bottom, b)
    True

    Note how since we fit the curve to simulated data where
    the bottom was 0.1 rather than 0, the midpoint and IC50
    are different. Specifically, the IC50 is larger than the
    midpoint, as you have to go past the midpoint to get
    down to value of 0.5 fraction surviving.

    >>> neut.ic50() > neut.midpoint
    True
    >>> scipy.allclose(neut.ic50(), 0.0337385586)
    True
    >>> scipy.allclose(0.5, neut.fracsurvive(neut.ic50()))
    True
    >>> neut.fracsurvive(neut.midpoint) > 0.5
    True

    Here is a plot of the curve and data points:

    >>> neut.plot('_fourParamLogistic_neutplot.png', 'example')

    .. image:: _static/_fourParamLogistic_neutplot.png
       :width: 2.4in
       :align: center

    Now here is an example where we constrain both the top
    and the bottom (to 1 and 0, respectively) and fit
    the curve. Now the midpoint and IC50 are the same:

    >>> b2 = 0
    >>> t2 = 1
    >>> fs2 = [fourParamLogistic.evaluate(c, m, s, b2, t2) for c in cs]
    >>> neut2 = fourParamLogistic(cs, fs2, fixbottom=b2)
    >>> scipy.allclose(neut2.midpoint, m)
    True
    >>> scipy.allclose(neut2.ic50(), m)
    True

    Now let's fit to concentrations that are all **less**
    than the midpoint, so that we never get anywhere
    close to complete neutralization. In this case,
    the estimated IC50 is unreliable, and so will be
    returned as `None`:
    
    >>> cs3 = [1e-5 * 2**x for x in range(7)]
    >>> (cs3[-1] < m)
    True
    >>> fs3 = [fourParamLogistic.evaluate(c, m, s, b2, t2) for c in cs3]
    >>> neut3 = fourParamLogistic(cs3, fs3, fixbottom=b2)
    >>> neut3.ic50() is None
    True

    However, we can still see a bound on the IC50
    using the `ic50_str` function. As seen below, this
    bound indicates that the IC50 exceeds the
    largest value in the concentrations used to fit
    the curve:

    >>> cs3[-1]
    0.00064
    >>> neut3.ic50_str()
    '$>0.00064$'

    """

    def __init__(self, cs, fs, fixbottom=False, fixtop=1):
        """See main class docstring."""
        # get data into arrays sorted by concentration
        self.cs = scipy.array(cs)
        self.fs = scipy.array(fs)
        self.fs = self.fs[self.cs.argsort()]
        self.cs = self.cs[self.cs.argsort()]

        # make initial guess for slope to have the right sign
        if self.fs[0] >= self.fs[-1]:
            self.slope = 1.5
        else:
            self.slope = -1.5

        # make initial guess for top and bottom
        if fixtop is False:
            if self.slope > 0:
                self.top = self.fs.max()
            else:
                self.top = self.fs.min()
        else:
            assert isinstance(fixtop, (int, float))
            self.top = fixtop
        if fixbottom is False:
            if self.slope > 0:
                self.bottom = self.fs.min()
            else:
                self.bottom = self.fs.max()
        else:
            assert isinstance(fixbottom, (int, float))
            self.bottom = fixbottom

        # make initial guess for midpoint
        midval = (self.top - self.bottom) / 2.0
        if (self.fs > midval).all():
            if self.slope > 0:
                self.midpoint = self.cs[-1]
            else:
                self.midpoint = self.cs[0]
        elif (self.fs <= midval).all():
            if self.slope > 0:
                self.midpoint = self.cs[0]
            else:
                self.midpoint = self.cs[-1]
        else:
            # get first index where f crosses midpoint
            i = scipy.argmax((self.fs > midval)[:-1] !=
                    (self.fs > midval)[1:])
            assert (self.fs[i] > midval) != (self.fs[i + 1] > midval)
            self.midpoint = (self.cs[i] + self.cs[i + 1]) / 2.0

        # set up function and initial guesses
        if fixtop is False and fixbottom is False:
            initguess = [self.midpoint, self.slope, self.bottom, self.top]
            func = self.evaluate
        elif fixtop is False:
            initguess = [self.midpoint, self.slope, self.top]
            def func(c, m, s, t):
                return self.evaluate(c, m, s, self.bottom, t)
        elif fixbottom is False:
            initguess = [self.midpoint, self.slope, self.bottom]
            def func(c, m, s, b):
                return self.evaluate(c, m, s, b, self.top)
        else:
            initguess = [self.midpoint, self.slope]
            def func(c, m, s):
                return self.evaluate(c, m, s, self.bottom, self.top)

        (popt, pcov) = scipy.optimize.curve_fit(
                func,
                self.cs,
                self.fs,
                initguess
                )

        if fixtop is False and fixbottom is False:
            (self.midpoint, self.slope, self.top, self.bottom) = popt
        elif fixtop is False:
            (self.midpoint, self.slope, self.top) = popt
        elif fixbottom is False:
            (self.midpoint, self.slope, self.bottom) = popt
        else:
            (self.midpoint, self.slope) = popt


    def ic50(self, extrapolate=False):
        """IC50 value.
        
        Concentration where `fracsurvive` is 0.5. Equals
        `midpoint` if and only if `top = 1` and `bottom = 0`.

        Args:
            `extrapolate` (bool)
                Do we extrapolate IC50 outside of range
                of data we fit? (Generally a bad idea.)

        Returns:
            A number giving the IC50 if the fitted value
            is in the range of concentrations used
            to fit the curve. Otherwise returns `None`
            unless `extrapolate` is `True`. Will still
            return `None` even if `extrapolate` is `True`
            if the fit parameters are such that the
            extrapolated curve never reaches 0.5.

        Calculated from:
        :math:`0.5 = b + \\frac{t - b}{1 + (ic50/m)^s}`,
        which solves to 
        :math:`ic50 = m \\times \left(\\frac{t - 0.5}{0.5 - b}\\right)^{1/s}`
        """
        if ((self.slope == 0) or (self.top == self.bottom) or
                ((self.top > 0.5) == (self.bottom > 0.5))):
            return None # extrapolated curve never hits 0.5
        ic50 = (self.midpoint * ((self.top - 0.5) / 
                (0.5 - self.bottom))**(1.0 / self.slope))
        if (self.cs[0] <= ic50 <= self.cs[-1]) or extrapolate:
            return ic50
        else:
            return None


    def ic50_str(self):
        """Returns string containing IC50.

        Differs from `ic50` in that it provides a string.
        This is useful because the string will indicate
        if the extrapolated IC50 is outside the 
        range of fitted data, such as by being: `> 0.5`.
        """

        def _sciNot(x):
            """Get number in LaTex scientific notation."""
            return dms_tools2.plot.latexSciNot([x])[0]

        ic50 = self.ic50(extrapolate=True)
        if ic50 is None:
            return 'NA'
        elif ic50 > self.cs[-1]:
            return '$>{0}'.format(_sciNot(self.cs[-1])[1 : ])
        elif ic50 < self.cs[0]:
            return '$<{0}'.format(_sciNot(self.cs[0])[1 : ])
        else:
            return _sciNot(ic50)


    def fracsurvive(self, c):
        """Fraction surviving at `c` for fitted parameters."""
        return self.evaluate(c, self.midpoint, self.slope,
                self.bottom, self.top)


    @staticmethod
    def evaluate(c, m, s, b, t):
        """Returns :math:`f(c) = b + \\frac{t - b}{1 + (c/m)^s}`."""
        return b + (t - b) / (1 + (c / m)**s)


    def plot(self, plotfile, samplename,
            ic50_in_name=True,
            xlabel='antibody concentration',
            ylabel='fraction surviving',
            fitpoints=100, cextend=2):
        """Plots neutralization points and fitted curve.

        Args:
            `plotfile` (str)
                Name of plot to create (e.g., PDF or PNG).
            `samplename` (str)
                Sample name (put at top of plot)
            `ic50_in_name` (bool)
                Include IC50 at top of plot with sample name?
            `xlabel` (str)
                x-axis label
            `ylabel` (str)
                y-axis label
            `fitpoints` (int)
                Number of points used to draw fit line.
            `cextend` (float)
                Concentrations extend this much fold
                below / above the min / max values used
                for fitting.
        """
        concentrations = scipy.concatenate(
                [self.cs,
                 scipy.logspace(math.log10(self.cs.min() / cextend),
                                math.log10(self.cs.max() * cextend),
                                num=fitpoints)
                ])
        n = len(concentrations)

        points = scipy.concatenate(
                [self.fs,
                 scipy.full(n - len(self.fs), scipy.nan)])

        fit = scipy.array([self.fracsurvive(c) for c in concentrations])

        if ic50_in_name:
            samplename += ' (IC50 = {0})'.format(self.ic50_str())

        neutdata = pandas.DataFrame({
                'concentration':concentrations,
                'sample':[samplename] * n,
                'points':points,
                'fit':fit,
                })
        dms_tools2.plot.plotFacetedNeutCurves(
                neutdata,
                plotfile,
                xlabel,
                ylabel)



if __name__ == '__main__':
    import doctest
    doctest.testmod()
