"""
Binds a python executable as a rez package.
"""
from __future__ import absolute_import
from rez.bind._utils import check_version, find_exe, extract_version, \
    make_dirs, log
from rez.package_maker__ import make_package
from rez.system import system


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="bind an interpreter other than the current "
                        "python interpreter")


def commands():
    global alias
    alias("python", "{this.exe}")


def bind(path, version_range=None, opts=None, parser=None):
    # find executable, determine version
    exepath = find_exe("python", opts.exe)
    code = "import sys;print('.'.join(str(x) for x in sys.version_info))"
    version = extract_version(exepath, ["-c", code])

    check_version(version, version_range)
    log("binding python: %s" % exepath)

    def make_root(variant, root):
        make_dirs(root, "python")

    with make_package("python", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["python"]
        pkg.commands = commands
        pkg.variants = [system.variant]
        pkg.exe = exepath

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
