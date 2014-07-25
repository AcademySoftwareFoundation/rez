from rez.contrib.animallogic.launcher.mode import Mode
from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.exceptions import BakerError
import datetime
import getpass
import time


class Baker(object):

    def __init__(self, launcher_service, rez_service):

        self.launcher_service = launcher_service
        self.rez_service = rez_service

        self.now = datetime.datetime.now()
        self.username = getpass.getuser()
        self.mode = Mode.shell
        self.operating_system = OperatingSystem.get_current_operating_system()
        self.settings = []

    def set_settings_from_launcher(self, source, preserve_system_settings=False):

        self.settings = self.launcher_service.get_settings_from_path(source, self.mode,  username=self.username, operating_system=self.operating_system, date=self.now)

        if not preserve_system_settings:
            self._strip_system_settings()

    def _strip_system_settings(self):

        self.filter_settings(lambda x : not x.is_system_setting())

    def _strip_system_package_settings(self):

        self.filter_settings(lambda x : not x.is_system_package_setting())

    def filter_settings(self, function):

        self.settings = filter(function, self.settings)

    def apply_overrides(self, overrides):

        for override in overrides:
            override_found = False

            for setting in self.settings:
                if setting.name == override.name:
                    setting.value = override.value
                    setting.setting_type = override.setting_type

                    override_found = True

            if not override_found:
                self.settings.append(override)

    def resolve_package_settings(self, max_fails=-1, preserve_system_package_settings=False):

        resolved_settings = []
        resolved_package_settings = self._get_resolved_package_settings(max_fails=max_fails)

        for setting in self.settings:
            if setting.setting_type not in (SettingType.package, SettingType.version):
                resolved_settings.append(setting)

        self.settings = resolved_settings + resolved_package_settings

        if not preserve_system_package_settings:
            self._strip_system_package_settings()

    def _get_resolved_package_settings(self, max_fails=-1):

        package_requests = self.get_package_requests_from_settings()
        timestamp = int(time.mktime(self.now.timetuple()))

        try:
            return self.rez_service.get_resolved_settings_from_requirements(package_requests, timestamp=timestamp, max_fails=max_fails)
        except Exception, e:
            raise BakerError(e)

    def get_package_requests_from_settings(self):

        package_requests = []

        for setting in self.settings:
            if setting.setting_type == SettingType.package:
                request = setting.get_setting_as_package_request()

                if request:
                    package_requests.append(request)

        return package_requests

    def create_new_preset_from_settings(self, destination, description=None):

        preset = self.launcher_service.create_preset(destination, description, username=self.username)

        self.launcher_service.add_settings_to_preset(self.settings, destination, username=self.username)

        return preset

