"""
Utilities related to process/script execution.
"""

from rez.vendor.six import six
from contextlib import contextmanager
import subprocess
import sys


@contextmanager
def add_sys_paths(paths):
    """Add to sys.path, and revert on scope exit.
    """
    original_syspath = sys.path[:]
    sys.path.extend(paths)

    try:
        yield
    finally:
        sys.path = original_syspath


if six.PY2:
    class _PopenBase(subprocess.Popen):
        def __enter__(self):
            return self
        def __exit__(self, exc_type, value, traceback):
            self.wait()

else:  # py3
    _PopenBase = subprocess.Popen


class Popen(_PopenBase):
    """subprocess.Popen wrapper.

    Allows for Popen to be used as a context in both py2 and py3.
    """
    def __init__(self, args, **kwargs):

        # Avoids python bug described here: https://bugs.python.org/issue3905.
        # This can arise when apps (maya) install a non-standard stdin handler.
        #
        # In newer version of maya and katana, the sys.stdin object can also
        # become replaced by an object with no 'fileno' attribute, this is also
        # taken into account.
        #
        if "stdin" not in kwargs:
            try:
                file_no = sys.stdin.fileno()
            except AttributeError:
                file_no = sys.__stdin__.fileno()

            if file_no not in (0, 1, 2):
                kwargs["stdin"] = subprocess.PIPE

        # Add support for the new py3 "text" arg, which is equivalent to
        # "universal_newlines".
        # https://docs.python.org/3/library/subprocess.html#frequently-used-arguments
        #
        if "text" in kwargs:
            kwargs["universal_newlines"] = True
            del kwargs["text"]

        super(Popen, self).__init__(args, **kwargs)
