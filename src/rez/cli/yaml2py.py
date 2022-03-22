# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Print a package.yaml file in package.py format.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "PATH", type=str, nargs='?',
        help="path to yaml to convert, or directory to search for package.yaml;"
        " cwd if not provided")


def command(opts, parser, extra_arg_groups=None):
    from rez.packages import get_developer_package
    from rez.serialise import FileFormat
    from rez.exceptions import PackageMetadataError
    import os.path
    import os
    import sys

    if opts.PATH:
        path = os.path.expanduser(opts.PATH)
    else:
        path = os.getcwd()

    try:
        package = get_developer_package(path, format=FileFormat.yaml)
    except PackageMetadataError:
        package = None

    if package is None:
        print("Couldn't load the package at %r" % path, file=sys.stderr)
        sys.exit(1)

    package.print_info(format_=FileFormat.py)
