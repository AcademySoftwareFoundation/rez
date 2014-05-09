from rez.resolved_context import ResolvedContext
from rez.cli.util import get_rxt_file
import os.path



def command(opts, parser=None):
    for path in opts.RXT:
        if not os.path.exists(path):
            open(path)  # raise IOError

    paths = opts.RXT or [get_rxt_file()]
    for path in paths:
        r = ResolvedContext.load(path)
        rxt_name = os.path.basename(path)
        r.add_to_suite(opts.DEST,
                       rxt_name=rxt_name,
                       prefix=opts.prefix,
                       suffix=opts.suffix,
                       verbose=opts.verbose)
