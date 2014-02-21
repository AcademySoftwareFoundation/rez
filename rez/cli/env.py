from rez.resolved_context import ResolvedContext
from rez.util import get_epoch_time_from_str
from rez.shells import get_shell_types
from rez.system import system
from rez.settings import settings
import sys



shells = get_shell_types()

def setup_parser(parser):
    parser.add_argument("--sh", "--shell", dest="shell", type=str, choices=shells,
                        help="target shell type, defaults to the current shell "
                        "(%s)" % system.shell)
    parser.add_argument("-r", "--rcfile", type=str,
                        help="source this file instead of the target shell's "
                        "standard startup scripts, if possible")
    parser.add_argument("-c", "--command", type=str,
                        help="read commands from string")
    parser.add_argument("-s", "--stdin", action="store_true",
                        help="read commands from standard input")
    parser.add_argument("--ni", "--no-implicit", dest="no_implicit",
                        action="store_true",
                        help="don't add implicit packages to the request")
    parser.add_argument("--nl", "--no-local", dest="no_local", action="store_true",
                        help="don't load local packages")
    parser.add_argument("-t", "--time", type=str,
                        help="ignore packages released after the given time. "
                        "Supported formats are: epoch time (eg 1393014494), "
                        "or relative time (eg -10s, -5m, -0.5h, -10d)")
    parser.add_argument("--rxt", "--context", dest="rxt", type=str,
                        help="use a previously saved context. Resolve settings, "
                        "such as PKG, --ni etc are ignored in this case")
    parser.add_argument("--force-rxt", dest="force_rxt", action="store_true",
                        help="when using --rxt, skip validation of the context")
    parser.add_argument("PKG", type=str, nargs='*',
                        help='packages to use in the target environment')


def command(opts, parser=None):
    if opts.rxt:
        rc = ResolvedContext.load(opts.rxt)
        if not opts.force_rxt:
            rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None
        pkg_paths = settings.nonlocal_packages_path if opts.no_local else None
        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit))

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      block=True)
    sys.exit(returncode)
