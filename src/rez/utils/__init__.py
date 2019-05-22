from contextlib import contextmanager
import sys
import warnings
from ..vendor.six import six


@contextmanager
def with_noop():
    yield


def reraise(exc, new_exc_cls=None, format_str=None):
    if new_exc_cls is None:
        six.reraise(*sys.exc_info())

    if format_str is not None:
        warnings.warn("Argument `reraise.format_str` is deprecated")

    type_, value, traceback = sys.exc_info()
    six.reraise(new_exc_cls, exc, traceback)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
