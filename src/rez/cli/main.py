"""
The main command-line entry point.
"""
import os
import sys
import argparse
from rez import __version__
import rez.sigint



class RezHelpFormatter(argparse.HelpFormatter):
    remainder_descs = {
        "BUILD_ARG": "[-- ARG [ARG ...] [-- ARG [ARG ...]]]"
    }

    # allow for more meaningful remainder desc than '...'
    def _format_args(self, action, default_metavar):
        if action.nargs == argparse.REMAINDER:
            desc = self.remainder_descs.get(default_metavar)
            return desc or "..."
        else:
            return super(RezHelpFormatter,self)._format_args(action, default_metavar)

    # show default value for options with choices
    def _get_help_string(self, action):
        help = action.help
        if action.choices and ('%(default)' not in action.help) \
            and (action.default is not None) and \
                (action.default is not argparse.SUPPRESS):
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help += ' (default: %(default)s)'
        return help


p = argparse.ArgumentParser(
    description='Rez command-line tool',
    formatter_class=RezHelpFormatter)
subps = p.add_subparsers(dest="cmd", metavar="COMMAND")
subparsers = {}


# lazily loads subcommands, gives faster load time
subcmd = (sys.argv[1:2] + [None])[0]

class subcommand(object):
    def __init__(self, fn):
        self.fn = fn if fn.__name__ == ("add_%s" % str(subcmd)) else None

    def __call__(self, *nargs):
        if self.fn:
            return self.fn(*nargs)

class hidden_subcommand(subcommand):
    pass


def _add_common_args(subp):
    subp.add_argument("--debug", dest="debug", action="store_true",
                      help=argparse.SUPPRESS)

def _subcmd_name(cli_name):
    if cli_name in ("exec",):
        return cli_name+'_'
    else:
        return cli_name.replace('-','_')


@subcommand
def add_settings(parser):
    parser.add_argument("-p", "--param", type=str,
                        help="print only the value of a specific parameter")
    parser.add_argument("--pp", "--packages-path", dest="pkgs_path", action="store_true",
                        help="print the package search path, including any "
                        "system paths")

@subcommand
def add_context(parser):
    from rez.system import system
    from rez.shells import get_shell_types
    formats = get_shell_types() + ['dict', 'actions']

    parser.add_argument("--req", "--print-request", dest="print_request",
                        action="store_true",
                        help="print only the request list, including implicits")
    parser.add_argument("--res", "--print-resolve", dest="print_resolve",
                        action="store_true",
                        help="print only the resolve list")
    parser.add_argument("-t", "--print-tools", dest="print_tools", action="store_true",
                        help="print a list of the executables available in the context")
    parser.add_argument("-g", "--graph", action="store_true",
                        help="display the resolve graph as an image")
    parser.add_argument("--pg", "--print-graph", dest="print_graph", action="store_true",
                        help="print the resolve graph as a string")
    parser.add_argument("--wg", "--write-graph", dest="write_graph", type=str,
                        metavar='FILE', help="write the resolve graph to FILE")
    parser.add_argument("--pp", "--prune-package", dest="prune_pkg", metavar="PKG",
                        type=str, help="prune the graph down to PKG")
    # TODO remove
    parser.add_argument("--pc", "--prune-conflict", dest="prune_conflict", action="store_true",
                        help="prune the graph down to show conflicts only")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print more information about the context. "
                        "Ignored if --interpret is used.")
    parser.add_argument("-i", "--interpret", action="store_true",
                        help="interpret the context and print the resulting code")
    parser.add_argument("-f", "--format", type=str, choices=formats,
                        help="print interpreted output in the given format. If "
                        "None, the current shell language (%s) is used. If 'dict', "
                        "a dictionary of the resulting environment is printed. "
                        "Ignored if --interpret is False" % system.shell)
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the context in an empty environment")
    parser.add_argument("FILE", type=str, nargs='?',
                        help="rex context file (current context if not supplied)")

def _bind_build_system(parser):
    import os
    from rez.build_system import get_valid_build_systems
    clss = get_valid_build_systems(os.getcwd())

    if len(clss) == 1:
        cls = iter(clss).next()
        cls.bind_cli(parser)
    elif clss:
        types = [x.name() for x in clss]
        parser.add_argument("-b", "--build-system", dest="buildsys",
                            type=str, choices=types,
                            help="the build system to use.")

def _bind_build_args(parser):
    parser.add_argument("BUILD_ARG", metavar="ARG", nargs=argparse.REMAINDER,
                        help="extra arguments to build system. To pass args to "
                        "a child build system also, list them after another "
                        "'--' arg.")

@subcommand
def add_build(parser):
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clear the current build before rebuilding.")
    parser.add_argument("-i", "--install", action="store_true",
                        help="install the build to the local packages path. "
                        "Use --prefix to choose a custom install path.")
    parser.add_argument("-p", "--prefix", type=str, metavar='PATH',
                        help="install to a custom path")
    parser.add_argument("-s", "--scripts", action="store_true",
                        help="create build scripts rather than performing the "
                        "full build. Running these scripts will place you into "
                        "a build environment, where you can invoke the build "
                        "system directly.")
    _bind_build_args(parser)
    _bind_build_system(parser)

@subcommand
def add_release(parser):
    parser.add_argument("-m", "--message", type=str,
                        help="commit message")
    parser.add_argument("--no-latest", dest="no_latest",
                        action="store_true",
                        help="allows release of version earlier than the "
                        "latest release.")
    _bind_build_args(parser)
    _bind_build_system(parser)

@subcommand
def add_env(parser):
    from rez.system import system
    from rez.shells import get_shell_types
    shells = get_shell_types()

    parser.add_argument("--sh", "--shell", dest="shell", type=str, choices=shells,
                        help="target shell type, defaults to the current shell "
                        "(%s)" % system.shell)
    parser.add_argument("--rcfile", type=str,
                        help="source this file instead of the target shell's "
                        "standard startup scripts, if possible")
    parser.add_argument("--norc", action="store_true",
                        help="skip loading of startup scripts")
    parser.add_argument("-c", "--command", type=str,
                        help="read commands from string")
    parser.add_argument("-s", "--stdin", action="store_true",
                        help="read commands from standard input")
    parser.add_argument("--ni", "--no-implicit", dest="no_implicit",
                        action="store_true",
                        help="don't add implicit packages to the request")
    parser.add_argument("--nl", "--no-local", dest="no_local", action="store_true",
                        help="don't load local packages")
    parser.add_argument("--paths", type=str, default=None,
                        help="set package search path")
    parser.add_argument("--nb", "--no-bootstrap", dest="no_bootstrap",
                        action="store_true",
                        help="don't load bootstrap packages")
    parser.add_argument("-t", "--time", type=str,
                        help="ignore packages released after the given time. "
                        "Supported formats are: epoch time (eg 1393014494), "
                        "or relative time (eg -10s, -5m, -0.5h, -10d)")
    parser.add_argument("-o", "--output", type=str, metavar="FILE",
                        help="store the context into an rxt file, instead of "
                        "starting an interactive shell. Note that this will "
                        "also store a failed resolve")
    parser.add_argument("-i", "--input", type=str, metavar="FILE",
                        help="use a previously saved context. Resolve settings, "
                        "such as PKG, --ni etc are ignored in this case")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="run in quiet mode")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="verbose mode, repeat for more verbosity")
    parser.add_argument("PKG", type=str, nargs='*',
                        help='packages to use in the target environment')

@subcommand
def add_wrap(parser):
    parser.add_argument("-p", "--prefix", type=str,
                        help="Tools prefix")
    parser.add_argument("-s", "--suffix", type=str,
                        help="Tools suffix")
    parser.add_argument("DEST", type=str,
                        help="Directory to write the wrapped environment into")
    parser.add_argument("RXT", type=str, nargs='*',
                        help="Context files to wrap")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose mode")

@subcommand
def add_tools(parser):
    pass

@subcommand
def add_exec(parser):
    from rez.system import system
    from rez.shells import get_shell_types
    formats = get_shell_types() + ['dict', 'actions']

    parser.add_argument("-f", "--format", type=str, choices=formats,
                        help="print output in the given format. If None, the "
                        "current shell language (%s) is used. If 'dict', a "
                        "dictionary of the resulting environment is printed. "
                        "If 'actions', an agnostic list of actions is printed."
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

@subcommand
def add_test(parser):
    parser.add_argument("--shells", action="store_true",
                        help="test shell invocation")
    parser.add_argument("--solver", action="store_true",
                        help="test package resolving algorithm")
    parser.add_argument("--cli", action="store_true",
                        help="test commandline tools")
    parser.add_argument("--formatter", action="store_true",
                        help="test rex string formatting")
    parser.add_argument("--commands", action="store_true",
                        help="test package commands")
    parser.add_argument("--rex", action="store_true",
                        help="test the rex command generator API")
    parser.add_argument("--build", action="store_true",
                        help="test the build system")
    parser.add_argument("-v", "--verbosity", type=int, default=2,
                        help="set verbosity level")

@subcommand
def add_bootstrap(parser):
    from rez.shells import get_shell_types
    from rez.system import system
    shells = get_shell_types()
    parser.add_argument("--install-path", dest="install_path", type=str,
                        help="create a bootstrapped install of Rez in the "
                        "given path")
    parser.add_argument("--sh", "--shell", dest="shell", type=str, choices=shells,
                        help="target shell type of the install, defaults to the "
                        "current shell (%s)" % system.shell)
    parser.add_argument("--force", action="store_true",
                        help="create a bootstrapped Rez install, even if "
                        "advised not to")

@hidden_subcommand
def add_forward(parser):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)

def _add_subcommand(cmd, help=""):
    fn = globals()["add_%s" % cmd]
    if isinstance(fn, hidden_subcommand) and (cmd != subcmd):
        return

    subp = subps.add_parser(cmd, help=help, formatter_class=RezHelpFormatter)
    _add_common_args(subp)
    fn(subp)
    subparsers[cmd] = subp


def run():
    _add_subcommand("settings",
                    "Print current rez settings.")
    _add_subcommand("context",
                    "Print information about the current rez context, or a "
                    "given context file.")
    _add_subcommand("build",
                    "Build a package from source.")
    _add_subcommand("release",
                    "Build a package from source and deploy it.")
    _add_subcommand("env",
                    "Open a rez-configured shell, possibly interactive.")
    _add_subcommand("wrap",
                    "Created a wrapped environment from one or more context files")
    _add_subcommand("tools",
                    "List the tools available in the current environment")
    _add_subcommand("exec",
                    "Execute some Rex code and print the interpreted result.")
    _add_subcommand("bootstrap",
                    "Rez installation-related operations.")
    _add_subcommand("test",
                    "Run unit tests.")
    _add_subcommand("forward")

    p.add_argument("-V", "--version", action="version",
                   version="Rez %s" % __version__)

    opts = p.parse_args()
    cmd = opts.cmd
    exec("from rez.cli.%s import command" % _subcmd_name(cmd))

    if opts.debug or os.getenv("REZ_DEBUG", "").lower() in ("1","true","on","yes"):
        from rez.util import set_rm_tmpdirs
        exc_type = None
        set_rm_tmpdirs(False)
    else:
        exc_type = Exception

    try:
        returncode = command(opts, subparsers[cmd])
    except NotImplementedError as e:
        import traceback
        raise Exception(traceback.format_exc())
    except exc_type as e:
        print >> sys.stderr, "rez: %s: %s" \
                             % (e.__class__.__name__, str(e))
        sys.exit(1)

    sys.exit(returncode or 0)
