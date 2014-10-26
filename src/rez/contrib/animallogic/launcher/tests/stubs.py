from rez.contrib.animallogic.launcher.setting import ReferenceSetting


class StubPresetProxy(object):

    PRESETS_PREFIX = '/presets'
    PRESET_REFERENCE_TABLE = {'/test/full/path': 1234, '/test/to/different/path/': 9999,
                              '/root/path' : 1111, '/test/path/replace': 7777}

    def __init__(self, settings={}, preset_path="", preset=None):

        self.settings = settings
        self.preset_path = self._strip_prefix_from_path(preset_path)
        self.preset = preset

        self.root_preset = {'/root/path': [{u'id': 1, u'presetId': {u'key': 1234}, u'name': u'Test'},
                                           {u'id': 2, u'presetId': {u'key': 9999}, u'name': u'base'}]}


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

    def addReference(self, destination_path, referencePath, username, description):

        if not all([destination_path, referencePath, username]):
            raise TypeError("")
        for path in [destination_path, referencePath]:
            if not self.PRESET_REFERENCE_TABLE.has_key(path):
                raise Exception("Preset %s does not exists" % path)

        newRef = {u'id': 1, u'presetId': {u'key': self.PRESET_REFERENCE_TABLE[referencePath]}, u'name': u'Test'}
        self.root_preset[destination_path].append(newRef)

        return ReferenceSetting(referencePath, self.PRESET_REFERENCE_TABLE[referencePath])

    def removeReference(self, destination_path, referencePath, username, description):

        if not all([destination_path, referencePath, username]):
            raise TypeError("")
        for path in [destination_path, referencePath]:
            if not self.PRESET_REFERENCE_TABLE.has_key(path):
                raise Exception("Preset %s does not exists" % path)

        for ref in self.root_preset[destination_path]:
            if ref['presetId']['key'] == self.PRESET_REFERENCE_TABLE[referencePath]:
                self.root_preset[destination_path].remove(ref)


        return ReferenceSetting(referencePath, self.PRESET_REFERENCE_TABLE[referencePath])

    def resolveReferenceSettingsForPath(self, path, date):

        if not all([path]):
            raise TypeError("")

        return self.root_preset[self._strip_prefix_from_path(path)]

    def getFullyQualifiedPresetName(self, presetId, date):

        if not presetId:
            raise TypeError("")
        for path, preset_id in self.PRESET_REFERENCE_TABLE.iteritems():
            if preset_id == presetId['key']:
                return path

        raise Exception("Preset ID does not exists")

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

