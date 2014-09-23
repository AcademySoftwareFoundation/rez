from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.setting import ValueSetting, ReferenceSetting
from rez.contrib.animallogic.launcher.preset import Preset
from rez.contrib.animallogic.launcher.exceptions import LauncherError


class LauncherServiceInterface(object):

    def get_settings_from_path(self, path, mode, username=None, operating_system=None, date=None):

        raise NotImplementedError

    def add_setting_to_preset(self, setting, preset_path, username=None):

        raise NotImplementedError

    def add_settings_to_preset(self, settings, preset_path, username=None):

        raise NotImplementedError

    def create_preset(self, preset_path, description, username=None):

        raise NotImplementedError


class LauncherHessianService(LauncherServiceInterface):

    PRESETS_PREFIX = '/presets'

    def __init__(self, preset_proxy, toolset_proxy):

        self._preset_proxy = preset_proxy
        self._toolset_proxy = toolset_proxy

        LauncherServiceInterface.__init__(self)

    def _is_preset_path(self, path):

        return path.startswith(self.PRESETS_PREFIX)

    def _strip_prefix_from_path(self, path):

        return path.replace(self.PRESETS_PREFIX, '')

    def _create_reference_from_dict(self, dict_):

        return  ReferenceSetting(str(dict_['name']), dict_['presetId']['key'], dict_['id'])


    def _create_setting_from_dict(self, dict_):

        setting_type = SettingType.create_from_launcher_type(dict_['type']['name'])

        valueSetting = ValueSetting(str(dict_['name']), dict_['value'], setting_type)
        valueSetting.id = dict_['id']
        valueSetting.source_preset_id = dict_['sourcePresetId']['key'] if dict_['sourcePresetId'] else None
        valueSetting.operating_system = OperatingSystem[dict_['opSystem']['name']] if dict_['opSystem'] else OperatingSystem['none']

        return valueSetting

    def _create_preset_from_dict(self, dict_):

        preset = Preset(dict_['fullyQualifiedName'])
        preset.description = dict_['description']
        preset.id = dict_['id']['key']
        preset.parent_id = dict_['parentId']['key']

        return preset

    def _setting_type_to_dict(self, setting_type):

        return {'name':setting_type.launcher_type}

    def _operating_system_to_dict(self, operating_system):

        return {'name':operating_system.name}

    def get_preset_full_path(self, presetId, date=None):
        """
        Return the full path to the preset given a presetIf
        @param presetId: the Id of the preset
        @param date: restrict the date from when the preset path is going to be retrieved.
        @return: s string with the full path to the preset
        """
        return self._preset_proxy.getFullyQualifiedPresetName(presetId, date)

    def get_references_from_path(self, path, username=None, date=None):
        """
        Retrieves all preset references from  an existing preset path
        @param path: launcher preset path where the reference would be added
        @param username: the user that triggered the change
        @param date: restrict the date from when the references are going to be retrieved.
                     default to None=latest version
        """
        if self._is_preset_path(path):
            try:
                references = self._preset_proxy.resolveReferenceSettingsForPath(username,
                                                                                self._strip_prefix_from_path(path),
                                                                                date)
            except Exception, e:
                raise LauncherError("Unable to retrieve references settings from '%s' - %s." % (path, e))
        else:
            raise LauncherError("Retrieve reference only valid for presets '%s' " % path)

        return [self._create_reference_from_dict(reference) for reference in references]


    def add_reference_to_preset_path(self, path, referencePath, username=None, description=None):
        """
        Adds a preset reference to an existing preset path
        @param path: launcher preset path where the reference would be added
        @param referencePath: a launcher preset path that would be added as a reference
        @param username: the user that triggered the change
        @param description: short description of the change
        """
        return self._preset_proxy.addReference(self._strip_prefix_from_path(path), self._strip_prefix_from_path(referencePath),
                                        username, description)

    def remove_reference_from_path(self, path, referencePath, username=None, description=None):
        """
        Removes a preset reference from  an existing preset path
        @param path: launcher preset path where the reference would be added
        @param referencePath: a launcher preset path that would be added as a reference
        @param username: the user that triggered the change
        @param description: short description of the change
        """

        return self._preset_proxy.removeReference(self._strip_prefix_from_path(path),
                                           self._strip_prefix_from_path(referencePath), username, description)

    def get_settings_from_path(self, path, mode, username=None, operating_system=None, date=None):

        operating_system_dict = self._operating_system_to_dict(operating_system)

        if self._is_preset_path(path):
            tag = None
            method = self._preset_proxy.resolveSettingsForPath
            args = (username, self._strip_prefix_from_path(path), tag, operating_system_dict, mode.name, date)

        else:
            method = self._toolset_proxy.resolveSettingsForPath
            args = (username, path, mode.name, operating_system_dict, date)

        try:
            settings = method(*args)
        except Exception, e:
            raise LauncherError("Unable to retrieve settings from '%s' - %s." % (path, e))
        return [self._create_setting_from_dict(setting) for setting in settings]

    def add_setting_to_preset(self, setting, preset_path, username=None):

        tags = None
        return self._preset_proxy.addSetting(self._strip_prefix_from_path(preset_path), setting.name, setting.value, self._setting_type_to_dict(setting.setting_type), username, tags)

    def add_settings_to_preset(self, settings, preset_path, username=None):

        for setting in settings:
            self.add_setting_to_preset(setting, preset_path, username=username)

    def create_preset(self, preset_path, description, username=None):

        parent_path, name = preset_path.rsplit('/', 1)

        try:
            parent_id = self._get_parent_id_for_preset_path(parent_path)
            result = self._preset_proxy.createPreset(username, parent_id, name, description)
        except Exception, e:
            raise LauncherError("Unable to create preset '%s' - %s." % (preset_path, e.message['message']))

        return self._create_preset_from_dict(result)

    def _get_parent_id_for_preset_path(self, preset_path, date=None):

        parent_path, name = self._strip_prefix_from_path(preset_path).rsplit('/', 1)
        clear_dates_for_python = True

        for preset_group_member in self._preset_proxy.getPresetGroupMembersByPath(parent_path, date, clear_dates_for_python):
            if preset_group_member['name'] == name:
                return preset_group_member['id']
