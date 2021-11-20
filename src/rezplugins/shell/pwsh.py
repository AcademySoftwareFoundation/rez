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


"""PowerShell Core 6+"""

from rez.utils.platform_ import platform_
from ._utils.powershell_base import PowerShellBase


class PowerShellCore(PowerShellBase):

    @classmethod
    def name(cls):
        return 'pwsh'

    @classmethod
    def file_extension(cls):
        return 'ps1'

    @classmethod
    def get_syspaths(cls):
        if platform_.name == "windows":
            return super(PowerShellCore, cls).get_syspaths()
        else:
            # TODO: Newer versions of pwsh will parse .profile via sh [1], so
            # we could use a similar technique as SH itself. For now, to
            # support older pwsh version we depend on SH on Unix-like platforms
            # directly.
            # [1] https://github.com/PowerShell/PowerShell/pull/10050
            from rezplugins.shell.sh import SH
            return SH.get_syspaths()


def register_plugin():
    # Platform independent
    return PowerShellCore
