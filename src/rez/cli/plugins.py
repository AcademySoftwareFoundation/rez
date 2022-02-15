# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Get a list of a package's plugins.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package to list plugins for")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import get_plugins
    from rez.config import config
    import os
    import os.path
    import sys

    config.override("warn_none", True)

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list = get_plugins(package_name=opts.PKG, paths=pkg_paths)
    if pkgs_list:
        print('\n'.join(pkgs_list))
    else:
        print("package '%s' has no plugins." % opts.PKG, file=sys.stderr)
