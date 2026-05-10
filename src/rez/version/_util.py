# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from itertools import groupby
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")


class VersionError(Exception):
    pass


class ParseException(Exception):
    pass


class _Common(object):
    def __str__(self) -> str:
        raise NotImplementedError

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __repr__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, str(self))


def dedup(iterable: Iterable[T]) -> Iterator[T]:
    """Removes duplicates from a sorted sequence."""
    for e in groupby(iterable):
        yield e[0]
