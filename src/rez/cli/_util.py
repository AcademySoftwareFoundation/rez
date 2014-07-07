import os
import os.path
import sys
from rez import __version__

current_rxt_file = os.getenv("REZ_RXT_FILE")
if current_rxt_file and not os.path.exists(current_rxt_file):
    current_rxt_file = None


def get_rxt_file(rxt_file=None, err=True):
    if rxt_file is None:
        rxt_file = current_rxt_file
        if err and (rxt_file is None):
            print >> sys.stderr, ("running Rez v%s.\n" + \
                "not in a resolved environment context.\n") % __version__
            sys.exit(1)
    return rxt_file

def error(msg):
    '''
    An error, formatted and printed to stderr
    '''
    sys.__stderr__.write("Error: %s\n" % msg)

def output(msg=''):
    '''
    A result, printed to stdout
    '''
    sys.__stdout__.write("%s\n" % msg)

def redirect_to_stderr(func):
    '''
    decorator to redirect output to stderr.
    This is useful
    '''
    def wrapper(*args, **kwargs):
        try:
            # redirect all print statements to stderr
            sys.stdout = sys.stderr
            return func(*args, **kwargs)
        finally:
            sys.stdout = sys.__stdout__
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
