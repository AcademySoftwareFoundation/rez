"""
View changes to a profile over time.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-n", type=int,
        help="only show the first N log entries.")
    parser.add_argument(
        "--since", type=str,
        help="only show log entries at or after the given time.")
    parser.add_argument(
        "--until", type=str,
        help="only show log entries at or before the given time.")
    parser.add_argument(
        "-t", "--tools", action="store_true",
        help="only show entries that changed the tools")
    parser.add_argument(
        "-p", "--packages", action="store_true",
        help="only show entries that changed the package requirements")
    parser.add_argument(
        "-e", "--effective", action="store_true",
        help="only show entries that changed the profile. Equivalent to -tp")
    parser.add_argument(
        "-i", "--ineffective", action="store_true",
        help="when using any of -e/-p/-t, this option will also show entries "
        "that did NOT cause a change")
    parser.add_argument(
        "-a", "--all", action="store_true",
        help="shortcut for -eiv")
    parser.add_argument(
        "--handle", type=str,
        help="only list the entry matching HANDLE")
    parser.add_argument(
        "--hh", "--highlight-handle", dest="highlight_handle", type=str,
        help="highlight the log entry matching HANDLE")
    parser.add_argument(
        "--vh", "--view-handle", dest="view_handle", type=str,
        help="view the contents of a particular file commit")
    parser.add_argument(
        "PROFILE",
        help="name of profile to view")


def command(opts, parser, extra_arg_groups=None):
    from rez.util import get_epoch_time_from_str
    from soma.production_config import ProductionConfig
    from soma.exceptions import ErrorCode
    from soma.file_store import FileStatus
    import sys

    if opts.all:
        opts.packages = True
        opts.tools = True
        opts.ineffective = True
        opts.verbose = True
    elif opts.effective:
        opts.packages = True
        opts.tools = True

    highlight_handle = False
    if opts.handle or opts.highlight_handle:
        opts.verbose = True
        if opts.handle and opts.highlight_handle:
            parser.error("choose --handle or --hh, not both")
        if opts.highlight_handle:
            opts.handle = opts.highlight_handle
            highlight_handle = True

    since = get_epoch_time_from_str(opts.since) if opts.since else None
    until = get_epoch_time_from_str(opts.until) if opts.until else None

    pc = ProductionConfig.get_current_config()
    profile = pc.profile(opts.PROFILE)

    if opts.view_handle:
        _, content, _, _, file_status = profile.file_log(opts.view_handle)
        if file_status == FileStatus.deleted:
            print >> sys.stderr, "the file was deleted at that time"
            sys.exit(ErrorCode.no_such_file_handle.value)
        else:
            print content.strip()
    elif opts.packages or opts.tools:
        profile.print_effective_logs(packages=opts.packages,
                                     tools=opts.tools,
                                     include_ineffective=opts.ineffective,
                                     limit=opts.n,
                                     since=since,
                                     until=until,
                                     handle=opts.handle,
                                     highlight_handle=highlight_handle,
                                     verbose=opts.verbose)
    else:
        profile.print_logs(limit=opts.n,
                           since=since,
                           until=until,
                           handle=opts.handle,
                           highlight_handle=highlight_handle,
                           verbose=opts.verbose)
