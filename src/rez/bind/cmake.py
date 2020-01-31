"""
Binds a cmake executable as a rez package.
"""
from __future__ import absolute_import
from rez.package_maker import make_package
from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.utils.platform_ import platform_
from rez.system import system
from rez.utils.lint_helper import env
import os.path


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="manually specify the cmake executable to bind.")


def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    exepath = find_exe("cmake", getattr(opts, "exe", None))
    version = extract_version(exepath, "--version",
                              word_index=2 if os.name == 'nt' else -1)
    check_version(version, version_range)

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        link = os.path.join(binpath, "cmake")
        platform_.symlink(exepath, link)

    with make_package("cmake", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["cmake"]
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
