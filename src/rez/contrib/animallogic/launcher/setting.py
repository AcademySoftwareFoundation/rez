from rez.contrib.animallogic.launcher.settingtype import SettingType

class Setting(object):

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
