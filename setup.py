from __future__ import with_statement
import fnmatch
import os
import os.path
import sys

if sys.version_info < (2,6):
    print >> sys.stderr, "install failed - requires python v2.6 or greater"
    sys.exit(1)

try:
    from setuptools import setup, find_packages
except ImportError:
    print >> sys.stderr, "install failed - requires setuptools"
    sys.exit(1)



def find_files(path, pattern):
    paths = []
    basepath = os.path.realpath(os.path.join("src", "rez"))
    path = os.path.join(basepath, path)

    for root,_,files in os.walk(path):
        files = [x for x in files if fnmatch.fnmatch(x, pattern)]
        files = [os.path.join(root, x) for x in files]
        paths += [x[len(basepath):].lstrip(os.path.sep) for x in files]

    return paths


with open("src/rez/__init__.py") as f:
    code = f.read()
loc = code.split('\n')
ver_loc = [x for x in loc if x.startswith("__version__")][0]
version = ver_loc.split()[-1].replace('"','')

scripts = [
    "rezolve",
    "rez",
    "rez-settings",
    "rez-build",
    "rez-release",
    "rez-env",
    "rez-context",
    "rez-suite",
    "rez-tools",
    "rez-interpret",
    "rez-test",
    "rez-bind",
    "bez",
    "_rez_fwd",
    "_rez_csh_complete"
]

setup(
    name="rez",
    version=version,
    description=("A cross-platform packaging system that can build and "
                 "install multiple version of packages, and dynamically "
                 "configure resolved environments at runtime."),
    keywords="package resolve version build install software management",
    long_description=None,
    url="https://github.com/nerdvegas/rez",
    author="Allan Johns",
    author_email="nerdvegas@gmail.com",
    license="LGPL",
    scripts=[os.path.join('bin', x) for x in scripts],
    include_package_data=True,
    package_dir = {'': 'src'},
    packages=find_packages('src', exclude=["tests"]),
    package_data = {
        'rez': \
            ['rezconfig'] + \
            ['README*'] + \
            find_files('_sys', '*.csh') +
            find_files('_sys', '*.sh') +
            find_files('tests/data', '*.*') +
            find_files('packages', '*.*'),
        'rezplugins': [
            'build_system/cmake_files/*.cmake',
        ]
    },
    classifiers = [
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development",
        "Topic :: System :: Software Distribution"
    ]
)
