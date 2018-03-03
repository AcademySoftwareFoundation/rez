"""Start a Python interpreter or execute a Python script.

This will happen within Rez's own execution context. You can pass keyword
arguments or flags by using a double dash: rez python FILE ARG -- --flag
"""


def setup_parser(parser, completions=False):
    """Set up command specific arguments.

    Args:
        parser (ArgumentParser): A preconfigured base parser we can add
            arguments to which are specific to this sub command.
        completions (bool): Generate command completions, if enabled.

    """
    parser.add_argument(
        '-i', '--interactive', action='store_true',
        help='inspect interactively after FILE has run')
    file_action = parser.add_argument(
        'file', metavar='FILE', type=str, nargs='?',
        help='python script to execute')
    parser.add_argument(
        'arg', metavar='ARG', type=str, nargs='*',
        help='arguments to python script')
    parser.add_argument('-c', help='python code to execute', dest='command')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        file_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=['*.py'])


def command(opts, parser, extra_arg_groups=None):
    """Run the main logic this command exposes.

    Args:
        opts (Namespace): The object with attributes, created when parsing the
            given arguments on the command line.
        parser (ArgumentParser): This commands parser which was set up via
            `setup_parser`.
        extra_arg_groups (list): All extra argument groups that were separated
            by `--` from the main command. For example
            `rez python -- --flag` will result in
            `extra_arg_groups = [['--flag']]`.

    """
    import subprocess
    import sys

    cmd = [sys.executable, '-E']

    if opts.interactive:
        cmd.append('-i')

    if opts.command:
        cmd.extend(['-c', opts.command])

    if opts.file:
        cmd.append(opts.file)
        cmd.extend(opts.arg or [])

    if extra_arg_groups:
        for group in extra_arg_groups:
            cmd.extend(group)

    p = subprocess.Popen(cmd)
    sys.exit(p.wait())


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
