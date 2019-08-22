"""Windows PowerShell 6+"""

from rez.shells import Shell
from rez.utils.platform_ import platform_
from rezplugins.shell.powershell import PowerShellBase
from rezplugins.shell.sh import SH


class PowerShellCore(PowerShellBase):

    @property
    def executable(cls):
        if cls._executable is None:
            cls._executable = Shell.find_executable('pwsh')
        return cls._executable

    @classmethod
    def name(cls):
        return 'pwsh'

    @classmethod
    def file_extension(cls):
        return 'ps1'

    @classmethod
    def get_syspaths(cls):
        # TODO: Clean dependency from SH
        if platform_.name == "windows":
            return super(PowerShellCore, cls).get_syspaths()
        else:
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
