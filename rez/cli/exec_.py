import os
from rez.util import pretty_env_dict
from rez.rex import RexExecutor, Python
from rez.system import system
from rez.shells import create_shell, get_shell_types



def command(opts, parser=None):
    with open(opts.FILE) as f:
        code = f.read()

    interp = None
    if opts.format is None:
        from rez.system import system
        interp = create_shell(system.shell)
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
