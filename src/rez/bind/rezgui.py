"""
Binds rez-gui as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.package_maker import make_package
from rez.bind._utils import check_version, make_dirs
from rez.system import system
from rez.vendor.version.version import Version
from rez.utils.lint_helper import env
from rez.utils.execution import create_executable_script
import shutil
import os.path


def setup_parser(parser):
    parser.add_argument(
        "--gui-lib", type=str, default="PyQt-4", metavar="PKG",
        help="manually specify the gui lib to use (default: %(default)s).")


def commands():
    env.PYTHONPATH.append('{this.root}')
    env.PATH.append('{this.root}/bin')


def rez_gui_source():
    from rez.cli._main import run
    run("gui")


def bind(path, version_range=None, opts=None, parser=None):
    rez_version = Version(rez.__version__)
    check_version(rez_version, version_range)

    rez_major_version = rez_version.trim(1)
    rez_major_minor_version = rez_version.trim(2)
    next_major = int(str(rez_major_version)) + 1
    rez_req_str = "rez-%s+<%d" % (str(rez_major_minor_version), next_major)

    gui_lib = getattr(opts, "gui_lib", "")

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezgui_path = os.path.join(site_path, "rezgui")
        shutil.copytree(rezgui_path, os.path.join(root, "rezgui"))

        # create rez-gui executable
        binpath = make_dirs(root, "bin")
        filepath = os.path.join(binpath, "rez-gui")
        create_executable_script(filepath, rez_gui_source)

    # create package
    with make_package("rezgui", path, make_root=make_root) as pkg:
        pkg.version = rez_version
        pkg.variants = [system.variant]
        pkg.commands = commands
        pkg.tools = ["rez-gui"]

        pkg.requires = [rez_req_str]
        if gui_lib:
            pkg.requires.append(gui_lib)

    return pkg.installed_variants


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
