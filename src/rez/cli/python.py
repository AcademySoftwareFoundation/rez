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
    import subprocess
    import sys

    cmd = [sys.executable, "-E"]

    for arg_group in (extra_arg_groups or []):
        cmd.extend(arg_group)

    if opts.FILE:
        cmd.append(opts.FILE)

    p = subprocess.Popen(cmd)
    sys.exit(p.wait())


