"""
Binds a python executable as a rez package.
"""
from __future__ import absolute_import
from rez.bind._utils import check_version, find_exe, extract_version, \
    make_dirs, log, run_python_command
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.lint_helper import env
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version
import shutil
import os.path


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="bind an interpreter other than the current "
                        "python interpreter")


def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    # find executable, determine version
    exepath = find_exe("python3", opts.exe)
    code = "import sys; print('.'.join(str(x) for x in sys.version_info))"
    version = extract_version(exepath, ["-c", code])

    check_version(version, version_range)
    log("binding python: %s" % exepath)


    # make the package
    #

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        link = os.path.join(binpath, "python3")
        platform_.symlink(exepath, link)


    with make_package("python3", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["python3"]
        pkg.commands = commands
        pkg.variants = [system.variant]

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
