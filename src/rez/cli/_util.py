import os
import os.path
import sys
import signal
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


_handled_int = False
_handled_term = False


def sigbase_handler(signum, frame):
    """"Kill all child procs."""
    os.killpg(os.getpgid(0), signum)
    sys.exit(1)


def sigint_handler(signum, frame):
    """Exit gracefully on ctrl-C."""
    global _handled_int
    if not _handled_int:
        _handled_int = True
        print >> sys.stderr, "Interrupted by user"
        sigbase_handler(signum, frame)


def sigterm_handler(signum, frame):
    """Exit gracefully on terminate."""
    global _handled_term
    if not _handled_term:
        _handled_term = True
        print >> sys.stderr, "Terminated by user"
        sigbase_handler(signum, frame)


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigterm_handler)
