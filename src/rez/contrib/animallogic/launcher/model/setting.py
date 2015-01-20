from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.member import Member
from rez.contrib.animallogic.launcher.util import DefaultFormatter
import datetime


class Setting(Member):

    def get_children(self, date, recursive=False):
        return []


class ReferenceSetting(Setting):
    def __init__(self, id_, parent_id, name, preset_id):
        super(ReferenceSetting, self).__init__(id_, parent_id, name, None, None)

        self.preset_id = preset_id

    def getMemberTypeShortIdentifier(self):
        return "r"

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

    def __init__(self, id_, parent_id, name, value, type_, operating_system):
        super(ValueSetting, self).__init__(id_, parent_id, name, None, None)

        self.value = value
        self.setting_type = type_
        self.operating_system = operating_system

        self._value_parent = None

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
        Is this setting a 'system package' setting and so protected by Rez.
        This generally identifies implicit packages in Rez that need special
        handling when it comes to baking etc.
        """

        return self.is_package_setting() and self.name in self.SYSTEM_PACKAGE_SETTING_NAMES

    def is_package_setting(self):

        return self.setting_type == SettingType.package

    def __repr__(self):

        return "<ValueSetting name=%s, value=%s, type=%s>" % (self.name, self.value, self.setting_type.name)

    def getMemberTypeShortIdentifier(self):
        return "v"

    @property
    def parent(self):
        if self._parent or self.parent_id is None:
            return self._parent

        self._parent = self._service.get_preset_from_id(self.parent_id, datetime.datetime.now())
        return self._parent

    @parent.setter
    def parent(self, parent):
        self._parent = parent

    @property
    def value_parent(self):
        return self._value_parent

    @value_parent.setter
    def value_parent(self, value_parent):
        self._value_parent = value_parent

    @property
    def path(self):
        tokens = []
        parent = self.parent

        while parent is not None:
            tokens.append(parent.name)
            parent = parent.parent

        return "/presets/" + "/".join(reversed(tokens))

    def format(self, specification):
        formatter = DefaultFormatter()
        
        if self.value_parent is not None:
            value_parent = self.value_parent.__dict__
            value_parent["path"] = self.value_parent.path

        else:
            value_parent = self.parent.__dict__
            value_parent["path"] = self.parent.path

        return formatter.format(specification, type=self.getMemberTypeShortIdentifier(),
                                path=self.path, value_parent=value_parent,
                                **self.__dict__)
