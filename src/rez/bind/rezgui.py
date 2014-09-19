"""
Binds rez-gui as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.package_maker_ import make_py_package, code_provider, root
from rez.bind_utils import check_version
from rez.exceptions import RezBindError
from rez.util import print_info
from rez.system import system
from rez.vendor.version.version import Version
from rez.bind import rez as rezbind
import shutil
import os.path
import sys


def setup_parser(parser):
    parser.add_argument("--gui-lib", type=str, default="PyQt-4",
                        help="manually specify the gui lib to use (PyQt or PySide).")


@code_provider
def commands():
    env.PYTHONPATH.append('{this.root}')
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    version = rez.__version__
    check_version(version, version_range)

    # before we start, we need to make sure rez itself is bound
    try:
        (rez_pkg, verstion_str) = rezbind.bind(path, version_range, opts, parser)
        print_info('created package %(rez_pkg)s-%(verstion_str)s in %(path)s'%locals())
    except (IOError, os.error), why:
        print_info('by-passing creation of rez-%(version)s'%locals())

    rez_version = Version(version)
    rez_major_version = str(rez_version.trim(1))
    gui_lib = getattr(opts, "gui_lib", "")

    py_version = tuple(sys.version_info[:2])
    py_require_str = "python-%d.%d" % py_version
    requires = list(system.variant) + [py_require_str] + [gui_lib]

    tool_name = 'rez-gui'

    # get tool content
    bin_path = os.path.dirname(sys.argv[0])
    tool_path = os.path.join(bin_path, tool_name)
    with open(tool_path) as fid:
        tool_content = fid.read()

    with make_py_package("rezgui", version, path) as pkg:
        pkg.set_requires("rez-%s" % rez_major_version)
        pkg.add_variant(*requires)
        pkg.set_tools(tool_name)
        pkg.set_commands(commands)
        pkg.add_python_tool(name=tool_name, body=tool_content, relpath=root("bin"))
        install_path = pkg.variant_path(0)

    # copy source
    rez_path = rez.__path__[0]
    site_path = os.path.dirname(rez_path)
    rezgui_path = os.path.join(site_path, "rezgui")

    shutil.copytree(rezgui_path, os.path.join(install_path, "rezgui"))

    return ("rezgui", version)


