class StubPresetProxy(object):

    def __init__(self, settings, preset):

        self.settings = settings
        self.preset = preset

    def resolveSettingsForPath(self, username, path, tag, operating_system, mode, date):

        if not all([username, path, operating_system, mode, date]):
            raise TypeError("")

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

    def __init__(self, settings):

        self.settings = settings

    def resolveSettingsForPath(self, username, path, mode, operating_system, date):

        if not all([username, path, mode, operating_system, date]):
            raise TypeError("")

        return self.settings


class StubRezService(object):

    def __init__(self, settings):

        self.settings = settings

    def get_resolved_settings_from_requirements(self, requirements):

        return self.settings
