# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import fnmatch
import os
import os.path
import sys
import logging
import tempfile
import platform
import shutil


try:
    from setuptools import setup, find_packages
    import distutils.command.build_scripts
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


SCRIPT_TEMPLATE = """#!/usr/bin/python -E
# -*- coding: utf-8 -*-
import re
import sys
from rez.cli._entry_points import {0}
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
    sys.exit({0}())
"""

class build_scripts(distutils.command.build_scripts.build_scripts):
    def finalize_options(self):
        super().finalize_options()
        self.build_dir = os.path.join(self.build_dir, "rez")

    def run(self):
        logging.getLogger().info("running rez's customized build_scripts command")

        scripts = []
        tmpdir = tempfile.mkdtemp("rez-scripts")

        os.makedirs(self.build_dir)

        for command in self.scripts:
            spec = get_specifications()[command]

            filename = "{0}.py".format(command)
            if platform.system() == "Windows":
                filename = "{0}-script.py".format(command)

            path = os.path.join(tmpdir, filename)
            with open(path, "w") as fd:
                fd.write(SCRIPT_TEMPLATE.format(spec["func"]))

            scripts.append(path)

            if platform.system() == "Windows":
                launcher = "t64.exe"
                if spec["type"] == "window":
                    launcher = "w64.exe"

                self.copy_file(
                    os.path.join("launcher", launcher),
                    os.path.join(self.build_dir, "{0}.exe".format(command))
                )

        prod_install_path = os.path.join(tmpdir, ".rez_production_install")
        with open(prod_install_path, "w") as fd:
            fd.write("# Production install installed with pip")

        scripts.append(prod_install_path)

        self.scripts = scripts
        return super().run()


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
    scripts=list(get_specifications().keys()),
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
            find_files('*', 'data') +
            find_files('*.exe', 'vendor/distlib'),
        'rezplugins':
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
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development",
        "Topic :: System :: Software Distribution"
    ],
    python_requires=">=3.7",
    cmdclass={"build_scripts": build_scripts},
)
