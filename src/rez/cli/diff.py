"""
Compare the source code of two packages.
"""


def setup_parser(parser, completions=False):
    PKG1_action = parser.add_argument(
        "PKG1", type=str,
        help='package to diff')
    PKG2_action = parser.add_argument(
        "PKG2", type=str, nargs='?',
        help='package to diff against. If not provided, the next highest '
        'versioned package is used')

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG1_action.completer = PackageCompleter
        PKG2_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.packages import get_package_from_string
    from rez.utils.diff_packages import diff_packages

    pkg1 = get_package_from_string(opts.PKG1)
    if opts.PKG2:
        pkg2 = get_package_from_string(opts.PKG2)
    else:
        pkg2 = None

    diff_packages(pkg1, pkg2)


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
