from rez.contrib.animallogic.launcher.mode import Mode
from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.setting import ValueSetting
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
        self.packages = []

    def set_settings_from_launcher(self, source, preserve_system_settings=False):

        settings = self.launcher_service.get_unresolved_settings_from_path(source,
                                                                           operating_system=self.operating_system,
                                                                           date=self.now)

        self.settings = self.launcher_service.resolve_settings(settings, only_packages=True)

        if not preserve_system_settings:
            self._strip_system_settings()

    def _strip_system_settings(self):

        self.filter_settings(lambda x: not x.is_system_setting())

    def _strip_system_package_settings(self):

        self.filter_settings(lambda x: not x.is_system_package_setting())

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

    def create_new_preset_from_settings(self, destination, description=None):

        preset = self.launcher_service.create_preset(destination, description,
                                                     username=self.username)

        self.launcher_service.add_settings_to_preset(self.settings, destination,
                                                     username=self.username)

        return preset

    def get_package_requests_from_settings(self):

        package_requests = []

        for setting in self.settings:
            if setting.setting_type == SettingType.package:
                request = setting.get_setting_as_package_request()

                if request:
                    package_requests.append(request)

        return package_requests

    def resolve_package_settings(self, max_fails=-1, 
                                 preserve_system_package_settings=False):

        self.packages = self._get_resolved_packages_from_settings(max_fails=max_fails)

        self._strip_package_and_version_settings()
        self.settings += self._get_settings_for_resolved_packages()

        if not preserve_system_package_settings:
            self._strip_system_package_settings()

    def _strip_package_and_version_settings(self):

        self.filter_settings(lambda x: x.setting_type not in (SettingType.package,
                                                              SettingType.version))

    def _get_settings_for_resolved_packages(self):

        settings = []

        for package in self.packages:
            settings.append(self._create_setting_from_package(package))

        return settings

    def _get_resolved_packages_from_settings(self, max_fails=-1):

        package_requests = self.get_package_requests_from_settings()
        timestamp = int(time.mktime(self.now.timetuple()))

        try:
            return self.rez_service.get_resolved_packages_from_requirements(package_requests,
                                                                            timestamp=timestamp,
                                                                            max_fails=max_fails)
        except Exception, e:
            raise BakerError(e)

    def _create_setting_from_package(self, package):

        setting = ValueSetting(package.name, "==%s" % (package.version),
                               SettingType.package)

        return setting
