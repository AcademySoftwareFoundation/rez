"""
Diff a profile at two different times.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-b", "--before", type=str,
        help="set diff source to the profile at the given time")
    parser.add_argument(
        "-a", "--after", type=str,
        help="set diff target to the profile at the given time. Defaults "
        "to the current time.")
    parser.add_argument(
        "-e", "--expanded", action="store_true",
        help="diff in expanded mode")
    parser.add_argument(
        "--il", "--ignore-locks", dest="ignore_locks", action="store_true",
        help="ignore any active locks")
    parser.add_argument(
        "PROFILE",
        help="name of profile to view")


def command(opts, parser, extra_arg_groups=None):
    from rez.util import get_epoch_time_from_str, diff_content
    from soma.production_config import ProductionConfig
    from StringIO import StringIO

    if not opts.before:
        parser.error("--before is required")

    def _content(arg):
        time_ = get_epoch_time_from_str(arg) if arg else None
        pc = ProductionConfig.get_current_config(time_=time_)
        profile = pc.profile(opts.PROFILE, ignore_locks=opts.ignore_locks)

        buf = StringIO()
        if opts.expanded:
            profile.dump(buf=buf, verbose=True)
        else:
            profile.print_simple_info(buf=buf)
        return buf.getvalue()

    content_before = _content(opts.before)
    content_after = _content(opts.after)
    before_label = "BEFORE_%s" % opts.before
    after_label = ("AFTER_%s" % opts.after) if opts.after else "NOW"
    diff_content(content_before, content_after, before_label, after_label)
