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
