"""
Binds rez itself as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.package_maker_ import make_py_package, code_provider
from rez.bind_utils import check_version
from rez.system import system
from rez.lint_helper import env
import shutil
import os.path
import sys


def setup_parser(parser):
    pass


@code_provider
def commands():
    env.PYTHONPATH.append('{this.root}')


def bind(path, version_range=None, opts=None, parser=None):
    version = rez.__version__
    check_version(version, version_range)

    py_version = tuple(sys.version_info[:2])
    py_require_str = "python-%d.%d" % py_version
    requires = list(system.variant) + [py_require_str]

    with make_py_package("rez", version, path) as pkg:
        pkg.add_variant(*requires)
        pkg.set_commands(commands)
        install_path = pkg.variant_path(0)

    # copy source
    rez_path = rez.__path__[0]
    site_path = os.path.dirname(rez_path)
    rezplugins_path = os.path.join(site_path, "rezplugins")

    shutil.copytree(rez_path, os.path.join(install_path, "rez"))
    shutil.copytree(rezplugins_path, os.path.join(install_path, "rezplugins"))

    return ("rez", version)
