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
Binds the python pip module as a rez package.
"""
from __future__ import absolute_import
from rez.bind import _pymodule


def bind(path, version_range=None, opts=None, parser=None):
    name = "pip"
    tools = ["pip"]

    variants = _pymodule.bind(name,
                              path=path,
                              version_range=version_range,
                              pure_python=False,
                              tools=tools)

    return variants
