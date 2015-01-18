from rez.contrib.animallogic.launcher.model.member import Member


class Preset(Member):

    PRESETS_PREFIX = '/presets'

    def __init__(self, id_, parent_id, name, created_by, created_on, version,
                 description, path):
        super(Preset, self).__init__(id_, parent_id, name, created_by,
                                     created_on)

        self.version = version
        self.description = description

        self._path = path

    def getMemberTypeShortIdentifier(self):
        return "p"

    @property
    def path(self):
        return self._path

    def resolve_settings(self, date, user, os, mode):
        settings = []

        path = self.path[len(self.PRESETS_PREFIX):] if self.path.startswith(self.PRESETS_PREFIX) else self.path

        for entity in proxy.resolveSettingsForPath(user, path, None, os, mode, date):
            setting = EntityMapper.map(entity)
            settings.append(setting)

        return settings

    def __repr__(self):

        return "<Preset id=%s, path=%s>" % (self.id, self.path)
