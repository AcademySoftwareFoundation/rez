"""
View the contents of a package.
"""


def setup_parser(parser, completions=False):
    formats = ("py", "yaml")
    parser.add_argument(
        "-f", "--format", default="yaml", choices=formats,
        help="format to print the package in")
    parser.add_argument(
        "-a", "--all", action="store_true",
        help="show all package data, including release-related fields")
    parser.add_argument(
        "-b", "--brief", action="store_true",
        help="do not print extraneous info, such as package uri")

    mutual_group = parser.add_mutually_exclusive_group()
    mutual_group.add_argument(
        "-d", "--developer", action="store_true",
        help="all to give a path as package name to view the package.py in this path")
    mutual_group.add_argument(
        "-c", "--current", action="store_true",
        help="show the package in the current context, if any")

    parser.add_argument(
        "-p", "--pretty", dest="pretty", action="store_true",
        help="Prints the fields in a pretty manner, by default they are printed in raw format")
    parser.add_argument(
        "-s", "--separator", type=str,
        help="Separator to be used when printing lists. defaults to empty space ")
    parser.add_argument(
        "--fields", nargs="*",
        help="only show the given fields")

    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="the package to view (can be a path if -d/--developer is given)")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.utils.formatting import PackageRequest
    from rez.serialise import FileFormat
    from rez.packages_ import iter_packages, get_developer_package
    from rez.status import status
    from rez.exceptions import PackageMetadataError
    import os
    import sys

    req = None
    if not opts.developer:
        req = PackageRequest(opts.PKG)

    if opts.current:
        context = status.context
        if context is None:
            print >> sys.stderr, "not in a resolved environment context."
            sys.exit(1)

        variant = context.get_resolved_package(req.name)
        if variant is None:
            print >> sys.stderr, "Package %r is not in the current context" % req.name
            sys.exit(1)

        package = variant.parent
    elif req:
        it = iter_packages(req.name, req.range)
        packages = sorted(it, key=lambda x: x.version)

        if not packages:
            print "no matches found"
            sys.exit(1)

        package = packages[-1]
    else:
        path = os.path.abspath(opts.PKG)
        if not os.path.exists(path):
            print "The path %r does not exist" % path
            sys.exit(-1)

        try:
            package = get_developer_package(path)
        except PackageMetadataError:
            print "There is no rez package at %s " % path
            print "Please provide a valid path to a directory containing a package.py file."
            sys.exit(-1)

    if not opts.brief:
        print "URI:"
        print package.uri

        print
        print "CONTENTS:"

    format_fields = ["fields", "pretty", "separator"]
    # If any of the --fields, --pretty and --separator argument are used, we want to use the
    # txt format.
    custom_format = any(getattr(opts, arg) != parser.get_default(arg) for arg in format_fields)
    if custom_format:
        format_ = FileFormat.txt
    elif opts.format == "py":
        format_ = FileFormat.py
    else:
        format_ = FileFormat.yaml
    package.print_info(format_=format_,
                       include_release=opts.all,
                       include_attributes=opts.fields,
                       skip_attributes=["preprocess"],
                       separator=opts.separator,
                       pretty=opts.pretty)


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
