from rez.vendor.enum import Enum
import platform

class OperatingSystem(Enum):

    linux   = 'linux'
    mac     = 'mac'
    windows = 'windows'
    none    = None

    @staticmethod
    def get_current_operating_system():

        name = platform.system().lower()

        if name == 'linux':
            return OperatingSystem.linux

        elif name == 'osx':
            return OperatingSystem.mac

        elif name == 'windows':
            return OperatingSystem.windows

        else:
            raise RuntimeError("Unable to determine the current operating system '%s'." % name)
