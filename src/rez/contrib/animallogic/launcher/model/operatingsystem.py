from rez.vendor.enum import Enum
from rez.platform_ import platform_


class OperatingSystem(Enum):

    linux   = 'linux'
    mac     = 'mac'
    windows = 'windows'
    none    = None

    @staticmethod
    def get_current_operating_system():

        if platform_.name == 'linux':
            return OperatingSystem.linux

        elif platform_.name == 'osx':
            return OperatingSystem.mac

        elif platform_.name == 'windows':
            return OperatingSystem.windows

        else:
            raise RuntimeError("Unable to determine the current operating system '%s'." % name)
