from rez.contrib.animallogic.launcher.settingtype import SettingType

class Setting(object):

    SYSTEM_SETTING_NAMES = ("opSystem", 
                            "username", 
                            "AL_LAUNCHER_PRESET", 
                            "AL_LAUNCHER_MODE", 
                            "AL_LAUNCHER_TIMESTAMP", 
                            "AL_DFS", 
                            "al-dfs")

    def __init__(self, name, value, setting_type):

        self.name = name
        self.value = value
        self.setting_type = setting_type
        self.id = None
        self.source_preset_id = None
        self.operating_system = None

    def get_setting_as_package_request(self):
        """
        If the setting is a SettingType.package, return a string representing 
        this settings as a Rez request.
        """

        if self.setting_type == SettingType.package:
            if self.value:
                return '%s-%s' % (self.name, self.value)

            else:
                return self.name

        return None

    def is_system_setting(self):
        """
        Is this setting a 'system' setting and so protected by Launcher.
        """

        return self.name in self.SYSTEM_SETTING_NAMES

    def is_package_setting(self):

        return self.setting_type == SettingType.package
