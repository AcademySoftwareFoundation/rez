from __future__ import print_function, with_statement

import fnmatch
import os
import os.path
import sys


try:
    from setuptools import setup, find_packages
    from setuptools.command import build_py
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


class BuildPyWithRezBinsPatch(build_py.build_py):

    def run(self):
        build_py.build_py.run(self)
        self.patch_rez_binaries()
        self.copy_completion_scripts()

    def _append(self, data_files):
        """Append `data_files` into `distribution.data_files`

        Just like how additional files be assigned with setup(data_files=[..]),
        but for those extra files that can only be created in build time, here
        is the second chance.

        The `data_files` specifies a sequence of (directory, files) pairs in
        the following way:

            setup(...,
                data_files=[('config', ['foo/cfg/data.cfg'])],
            )

        Each (directory, files) pair in the sequence specifies the installation
        directory and the files to install there.

        So in the example above, the file `data.cfg` will be installed to
        `config/data.cfg`.

        IMPORTANT:
        The directory MUST be a relative path. It is interpreted relative to
        the installation prefix (Python’s sys.prefix for system installations;
        site.USER_BASE for user installations).

        @param data_files: a sequence of (directory, files) pairs
        @return:
        """
        # will be picked up by `distutils.command.install_data`
        if self.distribution.data_files is None:
            self.distribution.data_files = data_files
        else:
            self.distribution.data_files += data_files

    def patch_rez_binaries(self):
        from rez.vendor.distlib.scripts import ScriptMaker

        self.announce("Generating rez bin tools...", level=3)

        # Create additional build dir for binaries, so they won't be handled
        # as regular builds under "build/lib".
        build_path = os.path.join("build", "rez_bins")
        self.mkpath(build_path)

        # Make binaries, referenced from rez's install.py
        maker = ScriptMaker(
            source_dir=None,
            target_dir=build_path
        )
        maker.executable = sys.executable
        rel_rez_bin_paths = maker.make_multiple(
            specifications=get_specifications().values(),
            options=dict(interpreter_args=["-E"])
        )

        # Add validation file as production rez install
        # Do not remove - rez uses this!
        validation_file = os.path.join(build_path, ".rez_production_install")
        with open(validation_file, "w") as vfn:
            vfn.write(_rez_version)
        rel_rez_bin_paths.append(validation_file)

        # Compute relative install path, to work with wheel.
        # Install path, e.g. "bin/rez" or "scripts/rez" on Windows.
        abs_rez_dir = os.path.join(os.path.dirname(sys.executable), "rez")
        rel_rez_dir = os.path.relpath(abs_rez_dir, sys.prefix)

        self._append([(rel_rez_dir, rel_rez_bin_paths)])

    def copy_completion_scripts(self):
        # find completion dir in rez package build
        src = os.path.join("build", "lib", "rez", "completion")

        self._append([
            # copy completion scripts into root of python installation for
            # ease of use.
            ("completion", [os.path.join(src, fn) for fn in os.listdir(src)])
        ])


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
        "build_py": BuildPyWithRezBinsPatch,
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
