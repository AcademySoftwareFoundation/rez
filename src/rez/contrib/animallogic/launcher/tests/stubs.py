from rez.contrib.animallogic.launcher.exceptions import LauncherError

class StubPresetProxy(object):

    PRESETS_PREFIX = '/presets'

    def __init__(self, settings={}, preset_path="", preset=None):

        self.settings = settings
        self.preset_path = self._strip_prefix_from_path(preset_path)
        self.preset = preset

    def _strip_prefix_from_path(self, path):

        return path.replace(self.PRESETS_PREFIX, '')

    def resolveSettingsForPath(self, username, path, tag, operating_system, mode, date):

        if not all([username, path, operating_system, mode, date]):
            raise TypeError("")

        if self.preset_path != path:
            raise Exception({'message':"The provided preset is invalid."})

        return  self.settings

    def addSetting(self, path, name, value, type_, username, tags):

        if not all([path, name, value, type_, username]):
            raise TypeError("")

        return name, value, type_

    def createPreset(self, username, parent_id, name, description):

        if not all([username, parent_id, name, description]):
            raise TypeError("")

        return self.preset

    def getPresetGroupMembersByPath(self, parent_path, date, clear_dates_for_python):

        id_ = self.preset['parentId']['key']
        name = self.preset['fullyQualifiedName'].split('/')[-2]

        return [{'name':name, 'id':id}]


class StubToolsetProxy(object):

    def __init__(self, settings={}, toolset_path=""):

        self.settings = settings
        self.toolset_path = toolset_path

    def resolveSettingsForPath(self, username, path, mode, operating_system, date):

        if not all([username, path, mode, operating_system, date]):
            raise TypeError("")

        if self.toolset_path != path:
            raise Exception({'message':"The provided toolset is invalid."})

        return self.settings


class StubPackage(object):

    def __init__(self, name, version, base=""):

        self.name = name
        self.version = version
        self.base = base


class StubRezService(object):

    def __init__(self, packages):

        self.packages = packages

    def get_resolved_packages_from_requirements(self, requirements, timestamp=None, max_fails=-1):

        if 'conflict' in requirements:
            raise Exception("The provided requirements are invalid.")

        return self.packages

