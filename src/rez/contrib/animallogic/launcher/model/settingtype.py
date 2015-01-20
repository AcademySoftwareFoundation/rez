from rez.vendor.enum import Enum

class SettingType(Enum):

    int     = ('tInt', int)
    boolean = ('tBoolean', bool)
    string  = ('tString', str)
    float   = ('tFloat', float)
    path    = ('tPath', str)
    package = ('tPackage', str)
    version = ('tVersion', str)

    def __init__(self, launcher_type, python_type):

        self.launcher_type = launcher_type
        self.python_type = python_type

    @staticmethod
    def create_from_launcher_type(launcher_type):
        """
        Return the enum that matches the provided launcher type (for example
        'tInt' would return SettingType.int.
        """

        for setting_type in SettingType:
            if setting_type.launcher_type == launcher_type:
                return setting_type

        raise RuntimeError("Unable to determine the setting type for '%s'." % launcher_type)
