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
