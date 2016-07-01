"""
Start a python interpreter or execute a python script within Rez's own execution context.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="inspect interactively after FILE has run")
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='?',
        help='python script to execute')
    parser.add_argument(
        "ARG", type=str, nargs='*',
        help='arguments to python script')
    parser.add_argument('-c', help="python code to execute", dest='command')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py"])


def command(opts, parser, extra_arg_groups=None):
    import subprocess
    import sys

    cmd = [sys.executable, "-E"]

    if opts.interactive:
        cmd.append("-i")

    if opts.command:
        cmd.extend(['-c', opts.command])

    if opts.FILE:
        cmd.append(opts.FILE)
        cmd.extend(opts.ARG or [])

    p = subprocess.Popen(cmd)
    p.wait()


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
