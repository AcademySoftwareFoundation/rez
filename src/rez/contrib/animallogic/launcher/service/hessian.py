from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.setting import ValueSetting, ReferenceSetting
from rez.contrib.animallogic.launcher.model.preset import Preset
from rez.contrib.animallogic.launcher.model.group import Group
from rez.contrib.animallogic.launcher.model.tool import Tool
from rez.contrib.animallogic.launcher.exceptions import LauncherError
from rez.contrib.animallogic.launcher.util import truncate_timestamp
from rez.contrib.animallogic.launcher.service.interface import LauncherServiceInterface
import datetime

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

    def _create_member_from_dict(self, dict_):

        return EntityMapper.map(dict_, self)

    def _setting_type_to_dict(self, setting_type):

        return {'name':setting_type.launcher_type}

    def _operating_system_to_dict(self, operating_system):

        return {'name':operating_system.name}

    def _get_parent_id_for_preset_path(self, preset_path, date=None):

        parent_path, name = self._strip_prefix_from_path(preset_path).rsplit('/', 1)
        clear_dates_for_python = True

        for preset_group_member in self._preset_proxy.getPresetGroupMembersByPath(parent_path, date, clear_dates_for_python):
            if preset_group_member['name'] == name:
                return preset_group_member['id']

    def get_preset_full_path(self, preset_id, date=None):
        """
        Return the full path to the preset given a presetIf
        @param presetId: the Id of the preset
        @param date: restrict the date from when the preset path is going to be retrieved.
        @return: s string with the full path to the preset
        """
        return self._preset_proxy.getFullyQualifiedPresetName({u'key': preset_id}, date)

    def get_references_from_path(self, path, date=None):
        """
        Retrieves all preset references from  an existing preset path
        @param path: launcher preset path where the reference would be added
        @param date: restrict the date from when the references are going to be retrieved.
                     default to None=latest version
        """
        if self._is_preset_path(path):
            try:
                references = self._preset_proxy.resolveReferenceSettingsForPath(self._strip_prefix_from_path(path),
                                                                                date)
            except Exception, e:
                raise LauncherError("Unable to retrieve references settings from '%s' - %s." % (path, e))
        else:
            raise LauncherError("Retrieve reference only valid for presets '%s' " % path)

        return [self._create_member_from_dict(reference) for reference in references]

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

        return [self._create_member_from_dict(setting) for setting in settings]

    def get_unresolved_settings_from_path(self, path, operating_system=None, date=None):

        operating_system_dict = self._operating_system_to_dict(operating_system)

        if not self._is_preset_path(path):
            raise LauncherError("This method is not support for toolset paths.")

        try:
            settings = self._preset_proxy.getFlattenedSettingListForPath(self._strip_prefix_from_path(path), operating_system_dict, date)
        except Exception, e:
            raise LauncherError("Unable to retrieve settings from '%s' - %s." % (path, e))

        return [self._create_member_from_dict(setting) for setting in settings]

    def resolve_settings(self, settings, only_packages=False):

        return SettingsResolver().resolve_settings(settings, only_packages=only_packages)

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

        return self._create_member_from_dict(result)

    def get_script_for_preset_path(self, preset_path, operating_system, command=None, username=None, date=None, mode=None):
        """
        Retrieves the python launch script for the specified tool. The resulting
        script contains both the generic environment setup script as well as each
        operating system specific launch command.
        """
        operating_system_dict = self._operating_system_to_dict(operating_system)
        overrides = None

        resolved_script = self._preset_proxy.resolveScriptForPath(username, preset_path, operating_system_dict, command, mode.name, date, overrides)

        return resolved_script["pythonExe"], resolved_script["scriptCode"]

    def resolve_preset_path(self, preset_path, date):
        """
        Resolves a preset path to a sequential list of preset elements (i.e.
        groups, tools and presets). The path specified should reference a valid
        list of preset elements by name where each element is the parent of the
        preceding element and should be seperated by a forward slash (/).
        """
        entities = self._preset_proxy.resolvePath(preset_path, date)
        return [self._create_member_from_dict(entity) for entity in entities]

    def get_preset_group_children(self, preset, date):
        """
        Retrieves the list of child members within a specified preset group at a
        specific date (and time).
        """
        children = []
        for entity in self._preset_proxy.getPresetGroupMembers({"key":preset.id}, date):
            child = self._create_member_from_dict(entity)
            children.append(child)
        return children

    def get_preset_group_from_id(self, id_):
        """
        Retrieves the preset group for the specified preset group ID.
        """
        entity = self._preset_proxy.getPresetGroup({"key":id_})
        return self._create_member_from_dict(entity)

    def get_preset_from_id(self, id_, date=None):
        """
        Retrieves the preset details for the specified preset ID at the
        specified date (and time).
        """
        return EntityMapper.map(self._preset_proxy.getPreset({"key":id_}, date), self)


class EntityMapper(object):

    @classmethod
    def map(cls, entity, service):
        # The results from Launcher don't provide a concrete way of determining
        # the type of entity (tool, group or preset) we are looking at - we just
        # get a dictionary of properties.  Fortunately some of the keys are
        # unique to the entity type so we can switch on those.
        if "presetId" in entity:
            id_ = entity["id"]
            name = entity["name"]
            preset_id = entity['presetId']['key']

            member = ReferenceSetting(id_, None, name, preset_id)

        elif "value" in entity:
            id_ = entity["id"]
            parent_id = entity["sourcePresetId"]["key"]
            name = entity["name"]
            value = entity["value"]
            type_ = SettingType.create_from_launcher_type(entity["type"]["name"])
            operating_system = OperatingSystem[entity['opSystem']['name']] if entity['opSystem'] else OperatingSystem['none']

            member = ValueSetting(id_, parent_id, name, value, type_, operating_system)

        else:
            id_ = entity["id"]["key"]
            parent_id = entity["parentId"]["key"] if entity["parentId"] else None
            name = entity["name"]
            created_by = entity["createdBy"]
            created_on = datetime.datetime.fromtimestamp(truncate_timestamp(entity["createdOn"]))

            if "fullyQualifiedName" in entity:
                version = entity["version"]
                description = entity["description"]
                path = entity["fullyQualifiedName"]

                member = Preset(id_, parent_id, name, created_by, created_on, version,
                              description, path)

            elif "iconPath" in entity:
                icon_path = entity["iconPath"]

                member = Tool(id_, parent_id, name, created_by, created_on, icon_path)

            else:
                member = Group(id_, parent_id, name, created_by, created_on)

        member.set_service(service)
        return member


class SettingsResolver(object):
    """
    Class to resolve the settings returned by the Launcher service.  This class
    can be used to resolve the ${...} style references Launcher provides when
    not fully resolving the variables internally.
    """

    def resolve_settings(self, settings, only_packages=False):

        resolved_settings = []

        for setting in settings:
            self._add_setting(resolved_settings, setting)

        return self._resolve_setting_values(resolved_settings, only_packages=only_packages)

    def _add_setting(self, settings, setting):
        replaced = False

        for i, next_ in enumerate(settings):
            if next_.name == setting.name:
                setting = self._check_for_reference_to_self(setting, next_.value)
                settings[i] = setting

                replaced = True
                break

        if not replaced:
            setting = self._check_for_reference_to_self(setting, "")
            settings.append(setting)

    def _check_for_reference_to_self(self, setting, old_value):

        if setting.value:
            name_reference = "${" + setting.name + "}"
            if name_reference in str(setting.value):
                setting.value = setting.value.replace(name_reference, old_value)

        return setting

    def _resolve_setting_values(self, settings, only_packages=False):
        resolved_settings = []

        for setting in settings:
            if only_packages and setting.setting_type != SettingType.package:
                resolved_settings.append(setting)
                continue

            modified = False
            value = setting.value

            if value and isinstance(value, basestring):
                index = value.find("${", 0)
                while index >= 0:
                    end = value.find("}", index + 2)
                    if (end > index):
                        reference = value[index + 2:end]
                        reference_setting = self._find_setting(settings, reference)
                        if reference_setting and "${" + reference + "}" not in reference_setting.value:
                            value = value[0:index] + reference_setting.value + value[end + 1:]
                            setting.value_parent = reference_setting.parent
                            modified = True
                        else:
                            index = end

                    index = value.find("${", index)

            if modified:
                setting.value = value
                resolved_settings.append(setting)

            else:
                resolved_settings.append(setting)

        return resolved_settings

    def _find_setting(self, settings, name):
        for setting in settings:
            if setting.name == name:
                return setting
