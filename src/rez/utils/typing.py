# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import absolute_import, print_function

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # FIXME: use typing.Protocol instead of this workaround when python 3.7 support is dropped
    from typing import Protocol

else:
    class Protocol(object):
        pass


class SupportsLessThan(Protocol):
    def __lt__(self, __other: Any) -> bool:
        pass
