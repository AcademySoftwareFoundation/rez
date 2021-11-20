# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
