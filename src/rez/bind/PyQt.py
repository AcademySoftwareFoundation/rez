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
Binds the python PyQt module as a rez package.
"""
from __future__ import absolute_import
from rez.bind import _pymodule
from rez.bind._utils import get_version_in_python


def bind(path, version_range=None, opts=None, parser=None):
    name = "PyQt"
    import_name = "PyQt4"
    tools = ["pyuic4"]

    version = get_version_in_python(
        name,
        ["from PyQt4 import QtCore",
         "print(QtCore.PYQT_VERSION_STR)"])

    variants = _pymodule.bind(name,
                              path=path,
                              import_name=import_name,
                              version_range=version_range,
                              requires=["sip-4"],
                              version=version,
                              pure_python=False,
                              tools=tools)

    return variants
