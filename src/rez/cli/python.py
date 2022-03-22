# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Start a python interpreter or execute a python script within Rez's own execution context.

Unrecognised args are passed directly to the underlying python interpreter.
"""


def setup_parser(parser, completions=False):
    file_action = parser.add_argument(
        "FILE", type=str, nargs='?',
        help='python script to execute')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        file_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py"])


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._main import is_hyphened_command
    from rez.utils.execution import Popen
    import sys

    # We need to skip first arg if 'rez-python' form was used, but we need to
    # skip the first TWO args if 'rez python' form was used.
    #
    if is_hyphened_command():
        args = sys.argv[1:]
    else:
        args = sys.argv[2:]

    cmd = [sys.executable, "-E"] + args

    with Popen(cmd) as p:
        sys.exit(p.wait())
