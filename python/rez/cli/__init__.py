'''
Utilities for cli tools
'''
import sys

def error(msg):
    '''
    An error, formatted and printed to stderr
    '''
    sys.__stderr__.write("Error: %s\n" % msg)

def output(msg):
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
