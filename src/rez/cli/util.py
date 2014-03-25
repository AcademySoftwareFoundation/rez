import os
import os.path
import sys
from rez import __version__



current_rxt_file = os.getenv("REZ_RXT_FILE")
if current_rxt_file and not os.path.exists(current_rxt_file):
    current_rxt_file = None


def get_rxt_file(rxt_file=None):
    if rxt_file is None:
        rxt_file = current_rxt_file
        if rxt_file is None:
            print >> sys.stderr, ("running Rez v%s.\n" + \
                "not in a resolved environment context.\n") % __version__
            sys.exit(1)
    return rxt_file
