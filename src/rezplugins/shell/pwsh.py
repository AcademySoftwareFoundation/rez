# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


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
