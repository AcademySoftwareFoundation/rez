'''
Open a rez-configured shell, possibly interactive.
'''
import select
import sys
import os
import os.path


def setup_parser(parser):
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
    # TODO: move verbose flag to top-level parser
    #parser.add_argument("-v", "--verbose", action="count", default=0,
    #                    help="verbose mode, repeat for more verbosity")
    parser.add_argument("PKG", type=str, nargs='*',
                        help='packages to use in the target environment')


def command(opts, parser):
    from rez.resolved_context import ResolvedContext
    from rez.util import get_epoch_time_from_str
    from rez.config import config

    if opts.input:
        rc = ResolvedContext.load(opts.input)
        if rc.status != "solved":
            print >> sys.stderr, "cannot rez-env into a failed context"
            sys.exit(1)

        rc.validate()
    else:
        t = get_epoch_time_from_str(opts.time) if opts.time else None

        if opts.paths is None:
            pkg_paths = (config.nonlocal_packages_path
                         if opts.no_local else None)
        else:
            pkg_paths = (opts.paths or "").split(os.pathsep)
            pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

        rc = ResolvedContext(opts.PKG,
                             timestamp=t,
                             package_paths=pkg_paths,
                             add_implicit_packages=(not opts.no_implicit),
                             add_bootstrap_path=(not opts.no_bootstrap),
                             verbosity=opts.verbose)

    success = (rc.status == "solved")
    if not success:
        rc.print_info(buf=sys.stderr)

    if opts.output:
        rc.save(opts.output)
        sys.exit(0 if success else 1)

    if not success:
        sys.exit(1)

    # generally shells will behave as though the '-s' flag was not present when
    # no stdin is available. So here we replicate this behaviour.
    if opts.stdin and not select.select([sys.stdin,] , [], [], 0.0)[0]:
        opts.stdin = False

    quiet = opts.quiet or bool(opts.command)

    returncode,_,_ = rc.execute_shell(shell=opts.shell,
                                      rcfile=opts.rcfile,
                                      norc=opts.norc,
                                      command=opts.command,
                                      stdin=opts.stdin,
                                      quiet=quiet,
                                      block=True)
    sys.exit(returncode)
