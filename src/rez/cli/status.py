'''
Report current status of the environment.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-t", "--print-tools", dest="print_tools", action="store_true",
        help="print a list of the executables currently available")


def command(opts, parser, extra_arg_groups=None):
    from rez.status import status
    import sys

    if opts.print_tools:
        b = status.print_tools(verbose=opts.verbose)
    elif not opts.verbose:
        b = status.print_brief_info()
    else:
        b = status.print_info(verbosity=opts.verbose - 1)
    sys.exit(0 if b else 1)
