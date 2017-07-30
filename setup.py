"""Setup script for ``dms_tools2``.

Written by Jesse Bloom.
"""

import sys
import os
import re
try:
    from setuptools import setup
    from setuptools import Extension
except ImportError:
    raise ImportError("You must install `setuptools`")

if not ((sys.version_info[0] == 2 and sys.version_info[1] == 7) or
        (sys.version_info[0] == 3 and sys.version_info[1] >= 4)):
    raise RuntimeError('phydms requires Python 2.7 or Python 3.4 or higher.\n'
            'You are using Python {0}.{1}'.format(
            sys.version_info[0], sys.version_info[1]))

# get metadata, which is specified in another file
metadata = {}
with open('dms_tools2/_metadata.py') as f:
	lines = f.readlines()
for dataname in ['version', 'author', 'author_email', 'url']:
    for line in lines:
        entries = line.split('=')
        assert len(entries) == 2, "Failed parsing metadata:\n{0}".format(line)
        if entries[0].strip() == '__{0}__'.format(dataname):
            if dataname in metadata:
                raise ValueError("Duplicate metadata for {0}".format(dataname))
            else:
                metadata[dataname] = entries[1].strip()[1 : -1]
    assert dataname in metadata, "Failed to find metadata {0}".format(dataname)

with open('README.rst') as f:
    readme = f.read()

# main setup command
setup(
    name = 'dms_tools2', 
    version = metadata['version'],
    author = metadata['author'],
    author_email = metadata['author_email'],
    url = metadata['url'],
    download_url = 'https://github.com/jbloomlab/dms_tools2/tarball/{0}'.format(
		metadata['version']), # assumes tagged version is on GitHub
    description = 'Deep mutational scanning (DMS) analysis tools.',
    long_description = readme,
    license = 'GPLv3',
    install_requires = [
        'biopython>=1.68',
        ],
    platforms = 'Linux and Mac OS X).',
    packages = ['dms_tools2'],
    package_dir = {'dms_tools2':'dms_tools2'},
#    ext_modules = [Extension('dms_tools2.cutils', ['dms_tools2/cutils.c'])],
    scripts = [
            'scripts/dms2_barcodedsubamplicons',
            ],
    package_data = {'dms_tools2':['_weblogo_template.eps']}, 
)