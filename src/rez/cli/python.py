"""
Start a python interpreter or execute a python script within Rez's own execution context.
This is only useful in a production Rez install, where Rez runs in its own isolated
environment. When you use rez-python, you will only be able to see the Rez python modules,
and any other python modules installed into the virtual env.

Use of rez-python is only expected by advanced users. You should never run rez-python
if you just want a standard python interpreter.
"""


def setup_parser(parser, completions=False):
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='?',
        help='python script to execute')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py"])


def run_interactive_session():
    import subprocess
    import sys
    p = subprocess.Popen([sys.executable])
    p.wait()


def command(opts, parser, extra_arg_groups=None):
    if not opts.FILE:
        run_interactive_session()
        return

    with open(opts.FILE) as f:
        code = f.read()
    pyc = compile(code, opts.FILE, "exec")
    exec(pyc, globals(), locals())
