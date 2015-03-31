from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.mode import Mode
from rez.contrib.animallogic.launcher.model.setting import Setting
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.syncer import Syncer
from rez.contrib.animallogic.launcher.cli.sync import update_sync_file
from rez.contrib.animallogic.launcher.exceptions import BakerError, RezResolverError
from rez.contrib.animallogic.launcher.cli.bake import argparse_setting
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy, StubRezService, StubPackage
from rez.vendor import argparse
import rez.vendor.unittest2 as unittest
import os
import tempfile


class TestSyncer(unittest.TestCase):

    def setUp(self):

        self.settings = [
                         {'name':'package_1', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 1, 'sourcePresetId':{'key':999}},
                         {'name':'package_2', 'value':'', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 2, 'sourcePresetId':{'key':999}},
                         {'name':'platform', 'value':'CentOS', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 3, 'sourcePresetId':{'key':999}},
                        ]
        self.preset_path = '/presets/Rez/test'
        self.resolved_packages = [StubPackage('package_1', '1.2.3', base='/film/tools/packages/package_1/1.2.3'),
                                  StubPackage('package_2', '2.0.1', base='/film/tools/packages/package_2/2.0.1'),
                                  StubPackage('platform', 'CentOS', base='/film/tools/packages/platform/CentOS')]

        self.launcher_service = LauncherHessianService(
                                                       StubPresetProxy(settings=self.settings,
                                                                       preset_path=self.preset_path,
                                                                       preset=None),
                                                       StubToolsetProxy())
        self.rez_service = StubRezService(self.resolved_packages)
        self.temp_fd, self.temp_name = tempfile.mkstemp()
        os.close(self.temp_fd)

    def tearDown(self):

        os.remove(self.temp_name)

    def test_get_sorted_paths_to_sync(self):

        syncer = Syncer(self.launcher_service, self.rez_service)

        syncer.bake_presets([self.preset_path])
        sorted_paths = syncer.get_sorted_paths_to_sync()
        expected = ['/film/tools/packages/package_1/1.2.3',
                    '/film/tools/packages/package_2/2.0.1',
                    '/film/tools/packages/platform/CentOS']

        self.assertEqual(expected, sorted_paths)

    def test_write_new_sync_file(self):

        os.remove(self.temp_name)

        syncer = Syncer(self.launcher_service, self.rez_service, relative_path="/film/")

        syncer.bake_presets([self.preset_path])
        sorted_paths = syncer.get_sorted_paths_to_sync()

        update_sync_file(self.temp_name, sorted_paths)
        self.assert_files_equal(os.path.join(os.path.dirname(__file__), "data", "sync_list_new.txt"))

    def test_write_sync_file_without_head_and_tail(self):

        with open(self.temp_name, "w") as fd:
            fd.writelines(["abc\n"])

        syncer = Syncer(self.launcher_service, self.rez_service, relative_path="/film/")

        syncer.bake_presets([self.preset_path])
        sorted_paths = syncer.get_sorted_paths_to_sync()

        update_sync_file(self.temp_name, sorted_paths)
        self.assert_files_equal(os.path.join(os.path.dirname(__file__), "data", "sync_list_without_head_and_tail.txt"))

    def test_write_sync_file_with_head_and_tail(self):

        with open(self.temp_name, "w") as fd:
            fd.writelines(["abc\n\n# Start Rez Automated Package Sync List.\ntools/packages/package_1/1.2.3\n# End Rez Automated Package Sync List.\n\ndef\n"])

        syncer = Syncer(self.launcher_service, self.rez_service, relative_path="/film/")

        syncer.bake_presets([self.preset_path])
        sorted_paths = syncer.get_sorted_paths_to_sync()

        update_sync_file(self.temp_name, sorted_paths)
        self.assert_files_equal(os.path.join(os.path.dirname(__file__), "data", "sync_list_with_head_and_tail.txt"))

    def assert_files_equal(self, expected_name):

        with open(self.temp_name) as fd:
            actual_lines = fd.readlines()

        with open(expected_name) as fd:
            expected_lines = fd.readlines()

        self.assertEqual(expected_lines, actual_lines)
