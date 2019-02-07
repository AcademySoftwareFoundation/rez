from contextlib import contextmanager
import sys


@contextmanager
def with_noop():
    yield


def reraise(exc, new_exc_cls=None, format_str=None):
    if new_exc_cls is None:
        raise

    if format_str is None:
        format_str = "%s"

    raise new_exc_cls, format_str % exc, sys.exc_info()[2]


