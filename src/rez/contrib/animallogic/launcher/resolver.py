from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.resolver import ResolverStatus
from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.exceptions import RezResolverError


class RezServiceInterface(object):

    def get_resolved_settings_from_requirements(self, requirements, max_fails=-1):

        raise NotImplementedError


class RezService(RezServiceInterface):

    def _create_setting_from_package(self, package):

        setting = Setting(package.name, str(package.version), SettingType.package)

        return setting

    def _get_package_settings_from_resolved_context(self, resolved_context):

        settings = []

        for package in resolved_context.resolved_packages:
            settings.append(self._create_setting_from_package(package))

        return settings

    def get_resolved_settings_from_requirements(self, requirements, timestamp=None, max_fails=-1):

        package_paths = [config.release_packages_path]

        resolved_context = ResolvedContext(requirements, package_paths, timestamp=timestamp, max_fails=max_fails)

        if resolved_context.status == ResolverStatus.solved:
            return self._get_package_settings_from_resolved_context(resolved_context)

        raise RezResolverError("Unable to resolve the environment for %s." % requirements)

