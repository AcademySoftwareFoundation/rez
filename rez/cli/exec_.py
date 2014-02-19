"""
Show current Rez settings
"""
import os
from rez.util import pretty_env_dict
from rez.rex import RexExecutor, Python
from rez.shells import create_shell, get_shell_types


formats = get_shell_types() + ['dict']

def setup_parser(parser):
    parser.add_argument("-f", "--format", type=str,
                        help="print output in the given format. If None, the "
                        "current shell language is used. If 'dict', a dictionary "
                        "of the resulting environment is printed. One of: %s"
                        % str(formats))
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the code in an empty environment")
    parser.add_argument("FILE", type=str,
                        help='file containing rex code to execute')


def command(opts, parser=None):
    with open(opts.FILE) as f:
        code = f.read()

    interp = None
    if opts.format is None:
        from rez.system import system
        interp = create_shell(system.shell)
    elif opts.format not in formats:
        parser.error("Invalid format specified, must be one of: %s" % str(formats))
    elif opts.format == 'dict':
        interp = Python(passive=True)
    else:
        interp = create_shell(opts.format)

    parent_env = {} if opts.no_env else None
    ex = RexExecutor(interpreter=interp, parent_environ=parent_env)
    ex.execute_code(code, filename=opts.FILE)
    o = ex.get_output()

    if isinstance(o, dict):
        print pretty_env_dict(o)
    else:
        print o
