# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import absolute_import, print_function, annotations

from typing import Any, Protocol


class SupportsLessThan(Protocol):
    def __lt__(self, __other: Any) -> bool:
        pass


class SupportsWrite(Protocol):
    def write(self, __s: str) -> object:
        pass


class SupportsRead(Protocol):
    def read(self) -> str:
        pass
