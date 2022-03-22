# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Run the Rez GUI application.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--diff", nargs=2, metavar=("RXT1", "RXT2"),
        help="open in diff mode with the given contexts")
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='*',
        help="context files")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter()


def command(opts, parser=None, extra_arg_groups=None):
    from rezgui.app import run
    run(opts, parser)
