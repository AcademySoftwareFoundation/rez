"""
List current profiles.
"""
from soma.production_config import ProductionConfig


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", dest="list_", action="store_true",
        help="list mode")
    parser.add_argument(
        "-t", "--tools", action="store_true",
        help="list tools")
    parser.add_argument(
        "-p", "--packages", action="store_true",
        help="list package overrides only (only used if PROFILE is set)")
    parser.add_argument(
        "-r", "--removals", action="store_true",
        help="show removals (only used if PROFILE is set)")
    parser.add_argument(
        "PROFILE", nargs='?',
        help="view profile")


def command(opts, parser, extra_arg_groups=None):
    pc = ProductionConfig.get_current_config()

    if opts.PROFILE:
        profile = pc.profile(opts.PROFILE)
        packages_ = opts.packages or not (opts.packages or opts.tools)
        tools_ = opts.tools or not (opts.packages or opts.tools)
        profile.print_info(packages=packages_,
                           tools=tools_,
                           removals=opts.removals,
                           verbose=opts.verbose)
    else:
        pc.print_info(list_mode=opts.list_, verbose=opts.verbose)
