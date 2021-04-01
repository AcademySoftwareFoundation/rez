'''
Disable a package so it is hidden from resolves.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-u", "--unignore", action="store_true",
        help="Unignore a package (no effect if not currently ignored).")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="the package to (un)ignore. Must be a specific package, eg 'foo-1.2.3'")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    pass
