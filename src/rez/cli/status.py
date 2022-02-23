# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


'''
Report current status of the environment, or a tool or package etc.
'''


def setup_parser(parser, completions=False):
    tools_action = parser.add_argument(
        "-t", "--tools", action="store_true",
        help="List visible tools. In this mode, OBJECT can be a glob pattern "
        "such as 'foo*'")
    parser.add_argument(
        "OBJECT", type=str, nargs='?',
        help="object to query - this could be a tool, package, context or suite."
        " If not provided, a summary of the current environment is shown.")

    if completions:
        from rez.cli._complete_util import ExecutablesCompleter
        tools_action.completer = ExecutablesCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.status import status
    import sys

    if opts.tools:
        b = status.print_tools(opts.OBJECT)
    else:
        b = status.print_info(opts.OBJECT)

    sys.exit(0 if b else 1)
