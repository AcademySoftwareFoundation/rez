"""
List profiles and tools.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", dest="list_", action="store_true",
        help="enable list mode")
    parser.add_argument(
        "-t", "--tools", action="store_true",
        help="list tools")
    parser.add_argument(
        "-L", "--locks", action="store_true",
        help="list locks")
    parser.add_argument(
        "--time", type=str,
        help="ignore profile updates after the given time. Supported formats "
        "are: epoch time (eg 1393014494), or relative time (eg -10s, -5m, "
        "-0.5h, -10d)")
    parser.add_argument(
        "PATTERN", nargs='?',
        help="filter results with glob-like pattern")


def command(opts, parser, extra_arg_groups=None):
    from rez.util import get_epoch_time_from_str
    from soma.production_config import ProductionConfig

    if opts.tools and opts.locks:
        parser.error("use --tools or --locks, not both")

    time_ = get_epoch_time_from_str(opts.time) if opts.time else None
    pc = ProductionConfig.get_current_config(time_=time_)

    if opts.tools:
        pc.print_tools(list_mode=opts.list_,
                       pattern=opts.PATTERN,
                       verbose=opts.verbose)
    elif opts.locks:
        pc.print_locks(list_mode=opts.list_,
                       verbose=opts.verbose)
    else:
        pc.print_profiles(list_mode=opts.list_,
                          pattern=opts.PATTERN,
                          verbose=opts.verbose)
