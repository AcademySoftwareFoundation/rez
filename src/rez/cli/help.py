"""
Utility for displaying help for the given package.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument("-m", "--manual", dest="manual", action="store_true",
                        default=False,
                        help="Load the rez technical user manual")
    parser.add_argument("-e", "--entries", dest="entries", action="store_true",
                        default=False,
                        help="Just print each help entry")
    PKG_action = parser.add_argument(
        "PKG", metavar='PACKAGE', nargs='?',
        help="package name")
    parser.add_argument("SECTION", type=int, default=1, nargs='?',
                        help="Help section to view (1..N)")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser=None, extra_arg_groups=None):
    from rez.utils.formatting import PackageRequest
    from rez.package_help import PackageHelp
    import sys

    if opts.manual or not opts.PKG:
        PackageHelp.open_rez_manual()
        sys.exit(0)

    request = PackageRequest(opts.PKG)
    if request.conflict:
        raise ValueError("Expected a non-conflicting package")

    help_ = PackageHelp(request.name, request.range, verbose=opts.verbose)
    if not help_.success:
        msg = "Could not find a package with help for %r." % request
        print(msg, file=sys.stderr)
        sys.exit(1)

    package = help_.package
    print("Help found for:")
    print(package.uri)
    if package.description:
        print()
        print("Description:")
        print(package.description.strip())
        print()

    if opts.entries:
        help_.print_info()
    else:
        try:
            help_.open(opts.SECTION - 1)
        except IndexError:
            print("No such help section.", file=sys.stderr)
            sys.exit(2)


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
