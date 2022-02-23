# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
View the contents of a package.
"""
from __future__ import print_function


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
    parser.add_argument(
        "-c", "--current", action="store_true",
        help="show the package in the current context, if any")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="the package to view")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.utils.formatting import PackageRequest
    from rez.serialise import FileFormat
    from rez.packages import iter_packages
    from rez.status import status
    import sys

    req = PackageRequest(opts.PKG)

    if opts.current:
        context = status.context
        if context is None:
            print("not in a resolved environment context.", file=sys.stderr)
            sys.exit(1)

        variant = context.get_resolved_package(req.name)
        if variant is None:
            print("Package %r is not in the current context" % req.name,
                  file=sys.stderr)
            sys.exit(1)

        package = variant.parent
    else:
        it = iter_packages(req.name, req.range)
        packages = sorted(it, key=lambda x: x.version)

        if not packages:
            print("no matches found")
            sys.exit(1)

        package = packages[-1]

    if not opts.brief:
        print("URI:")
        print(package.uri)

        print()
        print("CONTENTS:")

    if opts.format == "py":
        format_ = FileFormat.py
    else:
        format_ = FileFormat.yaml
    package.print_info(format_=format_, include_release=opts.all)
