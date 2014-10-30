"""
List current profiles.
"""
from soma.production_config import ProductionConfig


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", dest="list_", action="store_true",
        help="enable list mode")
    parser.add_argument(
        "-t", "--tools", action="store_true",
        help="list tools")
    parser.add_argument(
        "-p", "--packages", action="store_true",
        help="list a profile's package requests")
    parser.add_argument(
        "-r", "--removals", action="store_true",
        help="list a profile's removals")
    parser.add_argument(
        "NAME", nargs='?',
        help="either profile name, or glob-like pattern for profiles or tools")


def command(opts, parser, extra_arg_groups=None):
    pc = ProductionConfig.get_current_config()

    profile_name = None
    if opts.NAME and '*' not in opts.NAME:
        profile_name = opts.NAME

    if profile_name:
        profile = pc.profile(profile_name)
        profile.print_info(packages=(opts.packages or not opts.tools),
                           tools=opts.tools,
                           removals=opts.removals,
                           verbose=opts.verbose)
    else:
        pc.print_info(list_mode=opts.list_,
                      tools=opts.tools,
                      pattern=opts.NAME,
                      verbose=opts.verbose)
