"""
Creates the 'hello_world' testing package.

Note: Even though this is a python-based package, it does not list python as a
requirement. This is not typical! This package is intended as a very simple test
case, and for that reason we do not want any dependencies.
"""
from __future__ import absolute_import, print_function

from rez.package_maker import make_package
from rez.vendor.version.version import Version
from rez.utils.lint_helper import env
from rez.utils.execution import create_executable_script, ExecutableScriptMode
from rez.bind._utils import make_dirs, check_version
import os.path


def commands():
    env.PATH.append('{this.root}/bin')
    env.OH_HAI_WORLD = "hello"


def hello_world_source():
    import sys
    from optparse import OptionParser

    p = OptionParser()
    p.add_option("-q", dest="quiet", action="store_true",
                 help="quiet mode")
    p.add_option("-r", dest="retcode", type="int", default=0,
                 help="exit with a non-zero return code")
    opts, args = p.parse_args()

    if not opts.quiet:
        print("Hello Rez World!")
    sys.exit(opts.retcode)


def bind(path, version_range=None, opts=None, parser=None):
    version = Version("1.0")
    check_version(version, version_range)

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        filepath = os.path.join(binpath, "hello_world")

        create_executable_script(
            filepath,
            hello_world_source,
            py_script_mode=ExecutableScriptMode.platform_specific
        )

    with make_package("hello_world", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["hello_world"]
        pkg.commands = commands

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
