# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Binds rez itself as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.package_maker import make_package
from rez.bind._utils import check_version
from rez.system import system
from rez.utils.lint_helper import env
import shutil
import os.path


def commands():
    env.PYTHONPATH.append('{this.root}')


def bind(path, version_range=None, opts=None, parser=None):
    version = rez.__version__
    check_version(version, version_range)

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezplugins_path = os.path.join(site_path, "rezplugins")

        shutil.copytree(rez_path, os.path.join(root, "rez"))
        shutil.copytree(rezplugins_path, os.path.join(root, "rezplugins"))

    with make_package("rez", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.commands = commands
        pkg.requires = ["python-2.7+<4"]
        pkg.variants = [system.variant]

    return pkg.installed_variants
