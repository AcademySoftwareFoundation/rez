"""
Start a python interpreter or execute a python script within Rez's own execution context.
"""


def setup_parser(parser, completions=False):
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='?',
        help='python script to execute')
    parser.add_argument(
        "ARG", type=str, nargs='*',
        help='arguments to python script')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py"])


def command(opts, parser, extra_arg_groups=None):
    import sys

    if not opts.FILE:
        # run interactive interpreter
        import subprocess
        p = subprocess.Popen([sys.executable, "-E"])
        p.wait()
        return

    with open(opts.FILE) as f:
        code = f.read()
    pyc = compile(code, opts.FILE, "exec")

    sys.argv = opts.ARG or []
    exec(pyc, globals(), locals())
