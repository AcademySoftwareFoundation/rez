# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import sys
from contextlib import contextmanager


@contextmanager
def with_noop():
    yield


def reraise(exc, new_exc_cls):
    traceback = sys.exc_info()[2]

    # TODO test this.
    def reraise_(tp, value, tb=None):
        try:
            if value is None:
                value = tp()
            if value.__traceback__ is not tb:
                raise value.with_traceback(tb)
            raise value
        finally:
            value = None
            tb = None
    reraise_(new_exc_cls, exc, traceback)
