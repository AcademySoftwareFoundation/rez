from rez.contrib.animallogic.launcher.settingtype import SettingType


class Setting(object):

    def __init__(self, name, id=None):

        self.name = name
        self.id = id

    def __repr__(self):

        return "<Setting name=%s, id=%s>" % (self.name, self.id)


class ReferenceSetting(Setting):

    def __init__(self, name, presetId=None, id=None):

        super(ReferenceSetting, self).__init__(name, id)
        self.preset_id = presetId

    def __repr__(self):
        return "<ReferenceSetting name=%s, id=%s, presetId=%s>" % (self.name, self.id, self.preset_id)


class ValueSetting(Setting):

    SYSTEM_SETTING_NAMES = ("opSystem",
                            "username",
                            "AL_LAUNCHER_PRESET",
                            "AL_LAUNCHER_MODE",
                            "AL_LAUNCHER_TIMESTAMP",
                            "AL_DFS",
                            "al-dfs",)

    SYSTEM_PACKAGE_SETTING_NAMES = ("CentOS",
                                    "platform",
                                    "arch",
                                    "os",)

    def __init__(self, name, value, setting_type, operating_system=None):

        super(ValueSetting, self).__init__(name)
        self.value = value
        self.setting_type = setting_type
        self.source_preset_id = None
        self.operating_system = operating_system

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

    def is_system_package_setting(self):
        """
        Is this setting a 'system' setting and so protected by Launcher.
        """

        return self.is_package_setting() and self.name in self.SYSTEM_PACKAGE_SETTING_NAMES

    def is_package_setting(self):

        return self.setting_type == SettingType.package

    def __repr__(self):

        return "<ValueSetting name=%s, value=%s, type=%s>" % (self.name, self.value, self.setting_type.name)