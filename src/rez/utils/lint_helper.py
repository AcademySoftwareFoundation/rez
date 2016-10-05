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
