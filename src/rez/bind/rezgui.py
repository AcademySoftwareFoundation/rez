"""
Binds rez-gui as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.packages import iter_packages
from rez.package_maker_ import make_py_package, code_provider, root, get_code
from rez.bind_utils import check_version
from rez.exceptions import RezBindError
from rez.util import print_info
from rez.system import system
from rez.vendor.version.version import Version, VersionRange
from rez.bind import rez as rezbind
import shutil
import os.path
import sys


def setup_parser(parser):
    parser.add_argument(
        "--gui-lib", type=str, default="PyQt-4", metavar="PKG",
        help="manually specify the gui lib to use (default: %(default)s).")


@code_provider
def commands():
    env.PYTHONPATH.append('{this.root}')
    env.PATH.append('{this.root}/bin')


@code_provider
def rez_gui_bin():
    from rez.cli._main import run
    run("gui")


def bind(path, version_range=None, opts=None, parser=None):
    rez_version = Version(rez.__version__)
    rez_major_version = rez_version.trim(1)
    check_version(rez_version, version_range)

    # before we start, we need to make sure rez itself is bound
    range_ = VersionRange.from_version(rez_major_version)
    it = iter_packages("rez", range=range_, paths=[path])
    if next(it, False) is False:
        _, version_str = rezbind.bind(path, version_range, opts, parser)
        print_info("created package rez-%s" % version_str)

    gui_lib = getattr(opts, "gui_lib", "")
    py_version = tuple(sys.version_info[:2])
    py_require_str = "python-%d.%d" % py_version
    requires = list(system.variant) + [py_require_str] + [gui_lib]
    tool_name = 'rez-gui'

    # create package
    with make_py_package("rezgui", rez_version, path) as pkg:
        pkg.set_requires("rez-%s" % str(rez_major_version))
        pkg.add_variant(*requires)
        pkg.set_tools(tool_name)
        pkg.set_commands(commands)
        tool_content = get_code(rez_gui_bin)
        pkg.add_python_tool(name=tool_name, body=tool_content, relpath=root("bin"))
        install_path = pkg.variant_path(0)

    # copy source
    rez_path = rez.__path__[0]
    site_path = os.path.dirname(rez_path)
    rezgui_path = os.path.join(site_path, "rezgui")
    shutil.copytree(rezgui_path, os.path.join(install_path, "rezgui"))
    return ("rezgui", rez_version)
