"""
View or interact with a profile's environment.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--local", action="store_true",
        help="include local packages in the resolve (default: False)")
    parser.add_argument(
        "-p", "--print", dest="print_", action="store_true",
        help="just print info, rather than starting an interactive shell")
    parser.add_argument(
        "-o", "--output", type=str, metavar="FILE",
        help="store the profile's context into an rxt file, instead of starting "
        "an interactive shell. Note that this will also store a failed resolve")
    command_action = parser.add_argument(
        "-c", "--command", type=str,
        help="read commands from string. Alternatively, list command arguments "
        "after a '--'")
    parser.add_argument(
        "PROFILE",
        help="name of profile")


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from soma.production_config import ProductionConfig
    import sys

    pc = ProductionConfig.get_current_config()
    profile = pc.profile(opts.PROFILE)

    context = profile.context(include_local=opts.local,
                              verbosity=opts.verbose)

    if opts.output:
        context.save(opts.output)
        sys.exit(0 if context.success else 1)

    if not context.success:
        context.print_info(buf=sys.stderr)
        sys.exit(1)

    if opts.print_:
        context.print_info()
        return

    command = opts.command
    if extra_arg_groups:
        if opts.command:
            parser.error("argument --command: not allowed with arguments after '--'")
        command = extra_arg_groups[0] or None

    config.override("prompt", "%s>" % opts.PROFILE)
    returncode, _, _ = context.execute_shell(block=True,
                                             command=command,
                                             quiet=bool(command))
    sys.exit(returncode)
