"""
Diff a profile at two different times.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-e", "--expanded", action="store_true",
        help="diff in expanded mode")
    parser.add_argument(
        "PROFILE",
        help="name of profile to view")
    parser.add_argument(
        "BEFORE", type=str,
        help="set diff source to the profile at the given time")
    parser.add_argument(
        "AFTER", type=str, nargs='?',
        help="set diff target to the profile at the given time. Defaults "
        "to the current profile.")


def command(opts, parser, extra_arg_groups=None):
    from rez.util import get_epoch_time_from_str, diff_content
    from soma.production_config import ProductionConfig
    from StringIO import StringIO

    def _content(arg):
        time_ = get_epoch_time_from_str(arg) if arg else None
        pc = ProductionConfig.get_current_config(time_=time_)
        profile = pc.profile(opts.PROFILE)

        buf = StringIO()
        if opts.expanded:
            profile.dump(buf=buf, verbose=True)
        else:
            profile.print_simple_info(buf=buf)
        return buf.getvalue()

    content_before = _content(opts.BEFORE)
    content_after = _content(opts.AFTER)
    diff_content(content_before, content_after, "BEFORE", "AFTER")
