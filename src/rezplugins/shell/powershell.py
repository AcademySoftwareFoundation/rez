# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""Windows PowerShell 5"""

from rez.utils.platform_ import platform_
from ._utils.powershell_base import PowerShellBase


class PowerShell(PowerShellBase):

    @classmethod
    def name(cls):
        return 'powershell'

    @classmethod
    def file_extension(cls):
        return 'ps1'


def register_plugin():
    if platform_.name == "windows":
        return PowerShell
