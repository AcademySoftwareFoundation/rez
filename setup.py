from __future__ import with_statement
import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
except ImportError:
    print >> sys.stderr, "install failed - requires setuptools"
    sys.exit(1)


if sys.version_info < (2, 6):
    print >> sys.stderr, "install failed - requires python v2.6 or greater"
    sys.exit(1)


def find_files(pattern, path=None, root="rez"):
    paths = []
    basepath = os.path.realpath(os.path.join("src", root))
    path_ = basepath
    if path:
        path_ = os.path.join(path_, path)

    for root, _, files in os.walk(path_):
        files = [x for x in files if fnmatch.fnmatch(x, pattern)]
        files = [os.path.join(root, x) for x in files]
        paths += [x[len(basepath):].lstrip(os.path.sep) for x in files]

    return paths


# get version from source
with open("src/rez/utils/_version.py") as f:
    code = f.read().strip()
_rez_version = None  # just to keep linting happy
exec(code)  # inits _rez_version
version = _rez_version


scripts = [
    "rezolve",
    "rez",
    "rez-config",
    "rez-build",
    "rez-release",
    "rez-env",
    "rez-context",
    "rez-suite",
    "rez-interpret",
    "rez-python",
    "rez-selftest",
    "rez-bind",
    "rez-search",
    "rez-view",
    "rez-status",
    "rez-help",
    "rez-depends",
    "rez-memcache",
    "rez-yaml2py",
    "bez",
    "_rez_fwd",  # TODO rename this _rez-forward for consistency
    "_rez-complete",
    "rez-gui"
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
    zip_safe=False,
    package_dir = {'': 'src'},
    packages=find_packages('src', exclude=["build_utils",
                                           "build_utils.*",
                                           "tests"]),
    package_data = {
        'rez':
            ['rezconfig', 'utils/logging.conf'] +
            ['README*'] +
            find_files('*.*', 'completion') +
            find_files('*.*', 'tests/data'),
        'rezplugins':
            find_files('rezconfig', root='rezplugins') +
            find_files('*.cmake', 'build_system', root='rezplugins') +
            find_files('*.*', 'build_system/template_files', root='rezplugins'),
        'rezgui':
            find_files('rezguiconfig', root='rezgui') +
            find_files('*.*', 'icons', root='rezgui')
    },
    classifiers = [
        "Development Status :: 4 - Beta",
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

