'''
Execute some Rex code and print the interpreted result.
'''

def setup_parser(parser):
    from rez.shells import get_shell_types
    from rez.system import system

    formats = get_shell_types() + ['dict']

    parser.add_argument("-f", "--format", type=str, choices=formats,
                        help="print output in the given format. If None, the "
                        "current shell language (%s) is used. If 'dict', a "
                        "dictionary of the resulting environment is printed"
                        % system.shell)
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the code in an empty environment")
    parser.add_argument("--pv", "--parent-variables", dest="parent_vars",
                        type=str, metavar='VARS',
                        help="comma-seperated list of environment variables to "
                        "update rather than overwrite on first reference. If "
                        "this is set to the special value 'all', all variables "
                        "will be treated this way")
    parser.add_argument("FILE", type=str,
                        help='file containing rex code to execute')


def command(opts, parser=None):
    from rez.shells import create_shell
    from rez.util import pretty_env_dict
    from rez.rex import RexExecutor, Python

    with open(opts.FILE) as f:
        code = f.read()

    interp = None
    if opts.format is None:
        interp = create_shell()
    elif opts.format == 'dict':
        interp = Python(passive=True)
    else:
        interp = create_shell(opts.format)

    parent_env = {} if opts.no_env else None

    if opts.parent_vars == "all":
        parent_vars = True
    elif opts.parent_vars:
        parent_vars = [x for x in opts.parent_vars.split(',') if x]
    else:
        parent_vars = None

    ex = RexExecutor(interpreter=interp,
                     parent_environ=parent_env,
                     parent_variables=parent_vars,
                     bind_syspaths=False,
                     bind_rez=False)
    ex.execute_code(code, filename=opts.FILE)
    o = ex.get_output()

    if isinstance(o, dict):
        print pretty_env_dict(o)
    else:
        print o
