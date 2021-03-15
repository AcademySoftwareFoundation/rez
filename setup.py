from __future__ import print_function, with_statement

import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
    from setuptools.command import build_py
    from distutils.command import install_data
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


def patch_production_scripts(target_dir):
    from rez.utils.installer import create_rez_production_scripts
    scripts = create_rez_production_scripts(
        target_dir,
        specifications=get_specifications().values()
    )
    validation_file = os.path.join(target_dir, ".rez_production_install")
    with open(validation_file, "w") as vfn:
        vfn.write(_rez_version)

    return scripts + [validation_file]


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


class RezBuildPy(build_py.build_py):

    def run(self):
        build_py.build_py.run(self)
        self.patch_production_scripts()
        self.copy_completion_scripts()

    def _append(self, data_files):
        if self.distribution.data_files is None:
            self.distribution.data_files = []
        self.distribution.data_files += data_files

    def patch_production_scripts(self):
        # Create additional build dir for binaries, so they won't be handled
        # as regular builds under "build/lib".
        build_path = os.path.join("build", "rez_bins")
        self.mkpath(build_path)
        production_scripts = patch_production_scripts(build_path)
        self._append([
            # We don't know script install dir at this moment, therefore we
            # use a placeholder and pickup later.
            ("_production_script_:rez", production_scripts)
        ])

    def copy_completion_scripts(self):
        # find completion dir in rez package build
        src = os.path.join("build", "lib", "rez", "completion")
        self._append([
            # copy completion scripts into root of python installation for
            # ease of use.
            ("completion", [os.path.join(src, fn) for fn in os.listdir(src)])
        ])


class InstallData(install_data.install_data):

    def initialize_options(self):
        install_data.install_data.initialize_options(self)
        self.script_dir = None

    def finalize_options(self):
        install_data.install_data.finalize_options(self)
        self.set_undefined_options(
            'install', ('install_scripts', 'script_dir'),
        )

    def run(self):
        self.patch_production_scripts()
        install_data.install_data.run(self)

    def patch_production_scripts(self):
        data_files = []
        for dst, src in self.data_files:
            if dst.startswith("_production_script_:"):
                # Compute relative script install path
                sub_dir = dst.split(":")[-1]
                abs_dst_dir = os.path.join(self.script_dir, sub_dir)
                dst = os.path.relpath(abs_dst_dir, self.install_dir)
            data_files.append((dst, src))
        self.data_files[:] = data_files


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
    cmdclass={
        "build_py": RezBuildPy,
        "install_data": InstallData,
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
