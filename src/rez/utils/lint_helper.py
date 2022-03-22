# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
This file lets you import anything from it, and the result is a variable set to
None. It is only here to keep linters such as PyFlakes happy. It is used in cases
where code looks like it references an uninitialised variable, but does not.
"""
from types import ModuleType
import sys


class NoneModule(ModuleType):
    def __getattr__(self, name):
        return None

    def used(self, object_):
        """Use this to stop 'variable/module not used' linting errors."""
        pass


noner = NoneModule(__name__)


sys.modules[__name__] = noner
