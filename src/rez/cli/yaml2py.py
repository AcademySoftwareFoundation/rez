"""
Print a package.yaml file in package.py format.
"""


def setup_parser(parser, completions=False):
    PKG_action = parser.add_argument(
        "PATH", type=str, nargs='?',
        help="path to search for package.yaml, cwd if not provided")


def command(opts, parser, extra_arg_groups=None):
    from rez.packages_ import get_developer_package
    from rez.serialise import FileFormat
    import os.path
    import os
    import sys

    if opts.PATH:
        path = os.path.expanduser(opts.PATH)
    else:
        path = os.getcwd()
    if os.path.basename(path) == "package.yaml":
        path = os.path.dirname(path)

    filepath_yaml = os.path.join(path, "package.yaml")
    if not os.path.isfile(filepath_yaml):
        print >> sys.stderr, "Expected file '%s'" % filepath_yaml
        sys.exit(1)

    package = get_developer_package(path)
    if package is None:
        print >> sys.stderr, "Couldn't load the package at %r" % cwd
        sys.exit(1)

    package.print_info(format_=FileFormat.py)


# Copyright 2016 Allan Johns.
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
