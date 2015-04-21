'''
Open a rez-configured shell, possibly interactive.
'''


def setup_parser(parser, completions=False):
    from rez.vendor.argparse import SUPPRESS
    from rez.config import config
    from rez.system import system
    from rez.shells import get_shell_types

    shells = get_shell_types()

    parser.add_argument(
        "--shell", dest="shell", type=str, choices=shells,
        default=system.shell,
        help="target shell type (default: %(default)s)")
    parser.add_argument(
        "--rcfile", type=str,
        help="source this file instead of the target shell's standard startup "
        "scripts, if possible")
    parser.add_argument(
        "--norc", action="store_true",
        help="skip loading of startup scripts")
    command_action = parser.add_argument(
        "-c", "--command", type=str,
        help="read commands from string. Alternatively, list command arguments "
        "after a '--'")
    parser.add_argument(
        "-s", "--stdin", action="store_true",
        help="read commands from standard input")
    parser.add_argument(
        "--ni", "--no-implicit", dest="no_implicit",
        action="store_true",
        help="don't add implicit packages to the request")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't load local packages")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "-t", "--time", type=str,
        help="ignore packages released after the given time. Supported formats "
        "are: epoch time (eg 1393014494), or relative time (eg -10s, -5m, "
        "-0.5h, -10d)")
    parser.add_argument(
        "--max-fails", type=int, default=-1, dest="max_fails",
        metavar='N',
        help="abort if the number of failed configuration attempts exceeds N")
    parser.add_argument(
        "--time-limit", type=int, default=-1,
        dest="time_limit", metavar='SECS',
        help="abort if the resolve time exceeds SECS")
    parser.add_argument(
        "-o", "--output", type=str, metavar="FILE",
        help="store the context into an rxt file, instead of starting an "
        "interactive shell. Note that this will also store a failed resolve. "
        "If you use the special value '-', the context is written to stdout.")
    input_action = parser.add_argument(
        "-i", "--input", type=str, metavar="FILE",
        help="use a previously saved context. Resolve settings, such as PKG, "
        "--ni etc are ignored in this case")
    parser.add_argument(
        "-p", "--patch", action="store_true",
        help="patch the current context to create a new context")
    parser.add_argument(
        "--strict", action="store_true",
        help="strict patching. Ignored if --patch is not present")
    parser.add_argument(
        "--patch-rank", type=int, metavar="N", default=0,
        help="patch rank. Ignored if --patch is not present")
    parser.add_argument(
        "--no-cache", dest="no_cache", action="store_true",
        help="do not fetch cached resolves")
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="run in quiet mode (hides welcome message)")
    parser.add_argument(
        "--new-session", action="store_true",
        help="start the shell in a new process group")
    parser.add_argument(
        "--detached", action="store_true",
        help="open a separate terminal")
    parser.add_argument(
        "--pre-command", type=str, help=SUPPRESS)
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='*',
        help='packages to use in the target environment')
    extra_0_action = parser.add_argument(  # args after --
        "--N0", dest="extra_0", nargs='*',
        help=SUPPRESS)

    if completions:
        from rez.cli._complete_util import PackageCompleter, FilesCompleter, \
            ExecutablesCompleter, AndCompleter, SequencedCompleter
        command_action.completer = AndCompleter(ExecutablesCompleter, FilesCompleter())
        input_action.completer = FilesCompleter(dirs=False, file_patterns=["*.rxt"])
        PKG_action.completer = PackageCompleter
        extra_0_action.completer = SequencedCompleter(
            "extra_0", ExecutablesCompleter, FilesCompleter())


def command(opts, parser, extra_arg_groups=None):
    from rez.resolved_context import ResolvedContext
    from rez.resolver import ResolverStatus
    from rez.utils.formatting import get_epoch_time_from_str
    from rez.config import config
    import select
    import sys
    import os
    import os.path

    command = opts.command
    if extra_arg_groups:
        if opts.command:
            parser.error("argument --command: not allowed with arguments after '--'")
        command = extra_arg_groups[0] or None

    context = None
    request = opts.PKG
    t = get_epoch_time_from_str(opts.time) if opts.time else None

    if opts.paths is None:
        pkg_paths = (config.nonlocal_packages_path
                     if opts.no_local else None)
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    if opts.input:
        if opts.PKG:
            parser.error("Cannot use --input and provide PKG(s) at the same time")
        context = ResolvedContext.load(opts.input)
        if context.status != ResolverStatus.solved:
            print >> sys.stderr, "cannot rez-env into a failed context"
            sys.exit(1)

    if opts.patch:
        # TODO: patching is lagging behind in options, and needs to be updated
        # anyway.
        if context is None:
            from rez.status import status
            context = status.context
            if context is None:
                print >> sys.stderr, "cannot patch: not in a context"
                sys.exit(1)

        request = context.get_patched_request(request,
                                              strict=opts.strict,
                                              rank=opts.patch_rank)
        context = None

    if context is None:
        context = ResolvedContext(package_requests=request,
                                  timestamp=t,
                                  package_paths=pkg_paths,
                                  add_implicit_packages=(not opts.no_implicit),
                                  verbosity=opts.verbose,
                                  max_fails=opts.max_fails,
                                  time_limit=opts.time_limit,
                                  caching=(not opts.no_cache))

    success = (context.status == ResolverStatus.solved)
    if not success:
        context.print_info(buf=sys.stderr)

    if opts.output:
        if opts.output == '-':  # print to stdout
            context.write_to_buffer(sys.stdout)
        else:
            context.save(opts.output)
        sys.exit(0 if success else 1)

    if not success:
        sys.exit(1)

    # generally shells will behave as though the '-s' flag was not present when
    # no stdin is available. So here we replicate this behaviour.
    if opts.stdin and not select.select([sys.stdin], [], [], 0.0)[0]:
        opts.stdin = False

    quiet = opts.quiet or bool(command)
    returncode, _, _ = context.execute_shell(
        shell=opts.shell,
        rcfile=opts.rcfile,
        norc=opts.norc,
        command=command,
        stdin=opts.stdin,
        quiet=quiet,
        start_new_session=opts.new_session,
        detached=opts.detached,
        pre_command=opts.pre_command,
        block=True)

    sys.exit(returncode)
