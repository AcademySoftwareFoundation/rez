from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.setting import Setting
from rez.packages import iter_package_families
from rez.config import config
import logging
import os.path


logger = logging.getLogger(__name__)


class Syncer(object):

    VALID_EXT_LINK_ROOT = "/film"

    def __init__(self, launcher_service, rez_service, relative_path=None):

        self.launcher_service = launcher_service
        self.rez_service = rez_service

        self.relative_path = relative_path
        self.paths_to_sync = set()

    def bake_presets(self, presets, max_fails=-1, detect_ext_links=False):

        for preset in presets:
            baker = self._baker_factory()

            logger.info("Retrieving settings from Launcher %s." % preset)
            baker.set_settings_from_launcher(preset, preserve_system_settings=False)

            logger.info("Removing non-package settings.")
            baker.filter_settings(lambda x: x.is_package_setting())

            logger.info("Resolving package requests.")
            baker.resolve_package_settings(max_fails=max_fails,
                                           preserve_system_package_settings=False)

            logger.info("Resolved packages:")
            for package in baker.packages:
                logger.info("\t%s" % (package))

                relative_package_path = self._get_relative_base_path(package.base)
                self.paths_to_sync.add(relative_package_path)

                if detect_ext_links:
                    ext_link = self._find_ext_link_for_package(package)
                    if ext_link and ext_link.startswith(self.VALID_EXT_LINK_ROOT):
                        relative_ext_link_path = self._get_relative_base_path(ext_link)
                        self.paths_to_sync.add(relative_ext_link_path)

    def add_rez_package_path(self):

        logger.info("Finding rez package path.")

        rez_package_path = self._get_rez_package_path()
        if rez_package_path:
            self.paths_to_sync.add(self._get_relative_base_path(rez_package_path))

    def add_system_package_paths(self):

        logger.info("Finding system package paths.")

        system_package_paths = self._get_system_package_paths()
        for system_package_path in system_package_paths:
            self.paths_to_sync.add(self._get_relative_base_path(system_package_path))

    def log_paths_to_sync(self):

        logger.info("Paths to Sync:")
        for path in self.get_sorted_paths_to_sync():
            logger.info("\t%s" % (path))



    def get_sorted_paths_to_sync(self):

        return sorted(list(self.paths_to_sync))

    def _get_rez_package_path(self):

        return self._find_package_family_path("rez")

    def _get_system_package_paths(self):

        paths = set()

        for package_family_name in Setting.SYSTEM_PACKAGE_SETTING_NAMES:
            package_family_path = self._find_package_family_path(package_family_name)

            if package_family_path:
                paths.add(package_family_path)

        return paths

    def _find_package_family_path(self, package_family_name):

        package_paths = [config.release_packages_path]

        for package_family in iter_package_families(paths=package_paths):
            if package_family.name == package_family_name:
                package_family_path = os.path.join(package_family.search_path,
                                                   package_family.name)

                return package_family_path

    def _find_ext_link_for_package(self, package):

        ext_link = os.path.join(package.root, "ext")

        if os.path.islink(ext_link):
            return os.readlink(ext_link)

        return None

    def _get_relative_base_path(self, path):

        if not self.relative_path:
            return path

        if path.startswith(self.relative_path):
            return path.replace(self.relative_path, "")

        return path

    def _baker_factory(self):

        return Baker(self.launcher_service, self.rez_service)
