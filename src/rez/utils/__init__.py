# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import sys
from rez.vendor.six import six
from contextlib import contextmanager


@contextmanager
def with_noop():
    yield


def reraise(exc, new_exc_cls):
    traceback = sys.exc_info()[2]
    six.reraise(new_exc_cls, exc, traceback)
