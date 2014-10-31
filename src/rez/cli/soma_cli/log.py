"""
View changes to a profile over time.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-n", type=int,
        help="only show the first N log entries.")
    parser.add_argument(
        "--since", type=str,
        help="only show log entries starting with the most recent before the "
        "given time.")
    parser.add_argument(
        "--until", type=str,
        help="only show log entries at or before the given time.")
    parser.add_argument(
        "-e", "--effective", action="store_true",
        help="only print effective log entries - those that actually affect "
        "the profile. Note that this is an expensive operation.")
    parser.add_argument(
        "PROFILE",
        help="name of profile to view")


def command(opts, parser, extra_arg_groups=None):
    from rez.util import get_epoch_time_from_str
    from soma.production_config import ProductionConfig

    since = get_epoch_time_from_str(opts.since) if opts.since else None
    until = get_epoch_time_from_str(opts.until) if opts.until else None

    pc = ProductionConfig.get_current_config()
    profile = pc.profile(opts.PROFILE)

    if opts.effective:
        profile.print_effective_logs(limit=opts.n,
                                     since=since,
                                     until=until,
                                     verbose=opts.verbose)
    else:
        profile.print_logs(limit=opts.n,
                           since=since,
                           until=until,
                           verbose=opts.verbose)
