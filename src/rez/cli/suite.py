'''
Create a tool suite from one or more context files
'''
import os.path


def setup_parser(parser):
    parser.add_argument("-p", "--prefix", type=str,
                        help="Tools prefix")
    parser.add_argument("-s", "--suffix", type=str,
                        help="Tools suffix")
    parser.add_argument("DEST", type=str,
                        help="Directory to write the suite into")
    parser.add_argument("RXT", type=str, nargs='*',
                        help="Context files to add to the suite")


def command(opts, parser):
    from rez.resolved_context import ResolvedContext
    from rez.env import get_context_file

    paths = opts.RXT
    if not paths:
        current_context_file = get_context_file()
        if current_context_file:
            paths = [current_context_file]

    if not paths:
        print >> sys.stderr, ("running Rez v%s.\n" + \
            "not in a resolved environment context.\n") % __version__
        sys.exit(1)

    for path in paths:
        if not os.path.exists(path):
            open(path)  # raise IOError

    for path in paths:
        r = ResolvedContext.load(path)
        rxt_name = os.path.basename(path)
        r.add_to_suite(opts.DEST,
                       rxt_name=rxt_name,
                       prefix=opts.prefix,
                       suffix=opts.suffix,
                       verbose=opts.verbose)
