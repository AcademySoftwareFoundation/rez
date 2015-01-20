
class LauncherServiceInterface(object):

    def get_preset_full_path(self, preset_id, date=None):

        raise NotImplementedError

    def get_references_from_path(self, path, date=None):

        raise NotImplementedError

    def add_reference_to_preset_path(self, path, referencePath, username=None, description=None):

        raise NotImplementedError

    def remove_reference_from_path(self, path, referencePath, username=None, description=None):

        raise NotImplementedError

    def get_settings_from_path(self, path, mode, username=None, operating_system=None, date=None):

        raise NotImplementedError

    def get_unresolved_settings_from_path(self, path, operating_system=None, date=None):

        raise NotImplementedError

    def resolve_settings(self, settings, only_packages=False):

        raise NotImplementedError

    def add_setting_to_preset(self, setting, preset_path, username=None):

        raise NotImplementedError

    def add_settings_to_preset(self, settings, preset_path, username=None):

        raise NotImplementedError

    def create_preset(self, preset_path, description, username=None):

        raise NotImplementedError

    def get_script_for_preset_path(self, preset_path, operating_system, command=None, username=None, date=None, mode=None):

        raise NotImplementedError

    def get_preset_group_from_id(self, preset):

        raise NotImplementedError

    def get_preset_group_children(self, preset, date):

        raise NotImplementedError

    def resolve_preset_path(self, preset_path, date):

        raise NotImplementedError

    def get_preset_from_id(self, preset, date=None):

        raise NotImplementedError
