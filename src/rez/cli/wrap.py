'''
Created a wrapped environment from one or more context files
'''

import os.path

def setup_parser(parser):
    parser.add_argument("-p", "--prefix", type=str,
                        help="Tools prefix")
    parser.add_argument("-s", "--suffix", type=str,
                        help="Tools suffix")
    parser.add_argument("DEST", type=str,
                        help="Directory to write the wrapped environment into")
    parser.add_argument("RXT", type=str, nargs='*',
                        help="Context files to wrap")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose mode")

def command(opts, parser=None):
    from rez.resolved_context import ResolvedContext
    from rez.cli._util import get_rxt_file

    for path in opts.RXT:
        if not os.path.exists(path):
            open(path)  # raise IOError

    paths = opts.RXT or [get_rxt_file()]
    for path in paths:
        r = ResolvedContext.load(path)
        rxt_name = os.path.basename(path)
        r.create_wrapped_context(opts.DEST,
                                 rxt_name=rxt_name,
                                 prefix=opts.prefix,
                                 suffix=opts.suffix,
                                 verbose=opts.verbose)
