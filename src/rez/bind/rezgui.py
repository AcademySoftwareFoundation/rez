# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
