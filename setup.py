from __future__ import print_function, with_statement

import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
    from setuptools.command import install_scripts
except ImportError:
    print("install failed - requires setuptools", file=sys.stderr)
    sys.exit(1)


if sys.version_info < (2, 7):
    print("install failed - requires python v2.7 or greater", file=sys.stderr)
    sys.exit(1)


# carefully import some sourcefiles that are standalone
source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version
from rez.cli._entry_points import get_specifications


class InstallRezScripts(install_scripts.install_scripts):

    def run(self):
        install_scripts.install_scripts.run(self)
        self.patch_rez_binaries()

    def patch_rez_binaries(self):
        from rez.utils.installer import create_rez_production_scripts

        build_path = os.path.join(self.build_dir, "rez")
        install_path = os.path.join(self.install_dir, "rez")

        specifications = get_specifications().values()
        create_rez_production_scripts(build_path, specifications)

        validation_file = os.path.join(build_path, ".rez_production_install")
        with open(validation_file, "w") as vfn:
            # PEP-427, wheel will rewrite this *shebang* to the python that
            # used to install rez. And we'll use this to run rez cli tools.
            vfn.write("#!python\n")
            vfn.write(_rez_version)

        self.outfiles += self.copy_tree(build_path, install_path)


def find_files(pattern, path=None, root="rez", prefix=""):
    paths = []
    basepath = os.path.realpath(os.path.join("src", root))
    path_ = basepath
    if path:
        path_ = os.path.join(path_, path)

    for root, _, files in os.walk(path_):
        files = [x for x in files if fnmatch.fnmatch(x, pattern)]
        files = [os.path.join(root, x) for x in files]
        paths += [x[len(basepath):].lstrip(os.path.sep) for x in files]

    return [prefix + p for p in paths]


this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md')) as f:
    long_description = f.read()


setup(
    name="rez",
    version=_rez_version,
    description=("A cross-platform packaging system that can build and "
                 "install multiple version of packages, and dynamically "
                 "configure resolved environments at runtime."),
    keywords="package resolve version build install software management",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/nerdvegas/rez",
    author="Allan Johns",
    author_email="nerdvegas@gmail.com",
    license="LGPL",
    entry_points={
        "console_scripts": []
    },
    include_package_data=True,
    zip_safe=False,
    package_dir={'': 'src'},
    packages=find_packages('src', exclude=["build_utils",
                                           "build_utils.*",
                                           "tests"]),
    package_data={
        'rez':
            ['utils/logging.conf'] +
            ['README*'] +
            find_files('*', 'completion') +
            find_files('*', 'tests/data') +
            find_files('*.exe', 'vendor/distlib'),
        'rezplugins':
            find_files('rezconfig', root='rezplugins') +
            find_files('*.cmake', 'build_system', root='rezplugins') +
            find_files('*', 'build_system/template_files', root='rezplugins'),
        'rezgui':
            find_files('rezguiconfig', root='rezgui') +
            find_files('*', 'icons', root='rezgui')
    },
    data_files=[
        ("completion", find_files('*', 'completion', prefix='src/rez/'))
    ],
    cmdclass={
        "install_scripts": InstallRezScripts,
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development",
        "Topic :: System :: Software Distribution"
    ]
)
