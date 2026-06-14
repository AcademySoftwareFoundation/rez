# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
except ImportError:
    print("install failed - requires setuptools", file=sys.stderr)
    sys.exit(1)

# carefully import some sourcefiles that are standalone
source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version
from rez.cli._entry_points import get_specifications


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


this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md')) as f:
    long_description = f.read()


# Compile with mypyc only when explicitly requested via REZ_MYPYC=1. The
# default (and REZ_MYPYC=0) is a pure python build, regardless of python
# version. Requesting a mypyc build on a python that mypy does not support
# (< 3.10) is a hard error rather than a silent fallback.
use_mypyc = os.environ.get("REZ_MYPYC") == "1"

if use_mypyc and sys.version_info < (3, 10):
    raise RuntimeError(
        "Building rez with mypyc requires Python 3.10 or newer (mypy does "
        "not support older versions). Use Python >= 3.10, or set "
        "REZ_MYPYC=0 to build pure python."
    )

if use_mypyc:
    from mypyc.build import mypycify
    ext_modules = mypycify(
        [
            # "src/rez/package_filter.py",  # errors at runtime calling cached_property.uncache: "attribute 'cost' of 'PackageFilter' objects is not writable"
            "src/rez/solver.py",
            # "src/rez/resolved_context.py",  # error in copy().  need to rework from_dict()
            "src/rez/resolver.py",
            "src/rez/package_order.py",  # split out PackageOrderList from this module due to inheriting from list
            "src/rez/package_repository.py",
            "src/rez/package_resources.py",  # requires fixed version of mypyc
            "src/rez/version/__init__.py",
            "src/rez/version/_util.py",
            "src/rez/version/_requirement.py",
            "src/rez/version/_version.py",
            "src/rez/utils/formatting.py",  # includes a mixin, which should not be compiled
            # "src/rez/utils/memcached.py",
            "src/rez/utils/resources.py",
            # "src/rez/utils/scope.py",  # objects directly access/modify __dict__
            # "src/rez/vendor/schema/schema.py",
            "src/rezplugins/package_repository/filesystem.py",  # ConfigurationError at runtime with FileSystemPackageRepository plugin
        ],
        # only_compile_paths=["src/rez/solver.py"]
        opt_level="3",
        multi_file=True
    )
else:
    ext_modules = []


setup(
    name="rez",
    version=_rez_version,
    description=("A cross-platform packaging system that can build and "
                 "install multiple version of packages, and dynamically "
                 "configure resolved environments at runtime."),
    keywords="package resolve version build install software management",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/AcademySoftwareFoundation/rez",
    author="Allan Johns",
    author_email="nerdvegas@gmail.com",
    maintainer="Contributors to the rez project",
    maintainer_email="rez-discussion@lists.aswf.io",
    license="Apache-2.0",
    license_files=["LICENSE"],
    entry_points={
        "console_scripts": get_specifications().values()
    },
    include_package_data=False,
    zip_safe=False,
    package_dir={'': 'src'},
    packages=find_packages('src', exclude=["build_utils",
                                           "build_utils.*",
                                           "tests"]),
    install_requires=["mypy_extensions"],
    ext_modules=ext_modules,
    package_data={
        'rez':
            ['utils/logging.conf'] +
            ['README*'] +
            ["py.typed"] +
            find_files('*', 'completion') +
            find_files('*', 'data') +
            find_files('*.exe', 'vendor/distlib'),
        'rezplugins':
            ["py.typed"] +
            find_files('*.cmake', 'build_system', root='rezplugins') +
            find_files('*', 'build_system/template_files', root='rezplugins'),
        'rezgui':
            find_files('rezguiconfig', root='rezgui') +
            find_files('*', 'icons', root='rezgui')
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development",
        "Topic :: System :: Software Distribution"
    ],
    python_requires=">=3.8",
)
