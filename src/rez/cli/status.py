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
