# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


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
