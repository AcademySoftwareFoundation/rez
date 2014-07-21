from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.mode import Mode
from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.exceptions import BakerError, RezResolverError
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy, StubRezService
import rez.vendor.unittest2 as unittest


class TestBaker(unittest.TestCase):

    def setUp(self):

        self.package_preset_settings = [
                                        {'name':'package_1', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 1, 'sourcePresetId':{'key':999}},
                                        {'name':'package_2', 'value':'', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 2, 'sourcePresetId':{'key':999}},
                                       ]
        self.preset_settings = [
                                {'name':'string', 'value':'Hello, World!', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                {'name':'int', 'value':123, 'opSystem':None, 'type':{'name':'tInt'}, 'id': 4, 'sourcePresetId':{'key':999}},
                               ]

        self.new_preset = {'fullyQualifiedName':'/presets/Rez/test_new', 'description':'bar', 'parentId':{'key':43325883}, 'id':{'key':4077}, 'name':'test_new'}
        self.preset_path = '/presets/Rez/test'
        self.new_preset_path = '/presets/Rez/test_new'
        self.package_requests = ['package_1-1.2.3', 'package_2']
        self.resolved_package_settings = [Setting('package_1', '1.2.3', SettingType.package), Setting('package_2', '2.0.1', SettingType.package)]

        launcher_service = LauncherHessianService(StubPresetProxy(settings=self.package_preset_settings + self.preset_settings, preset_path=self.preset_path, preset=self.new_preset), StubToolsetProxy())
        rez_service = StubRezService(self.resolved_package_settings)
        self.baker = Baker(launcher_service, rez_service)

    def assert_setting(self, expected, setting):

        self.assertEqual(expected['name'], setting.name)
        self.assertEqual(expected['value'], setting.value)
        self.assertEqual(expected['opSystem'], setting.operating_system.value)
        self.assertEqual(expected['type']['name'], setting.setting_type.launcher_type)
        self.assertEqual(expected['id'], setting.id)
        self.assertEqual(expected['sourcePresetId']['key'], setting.source_preset_id)

    def assert_settings(self, expected_settings, settings):

        self.assertEqual(len(expected_settings), len(settings))
        for expected_setting, setting in zip(expected_settings, settings):
            self.assert_setting(expected_setting, setting)

    def test_get_package_requests_from_settings(self):

        package_settings = self.baker.get_package_settings_from_launcher(self.preset_path)
        self.assert_settings(self.package_preset_settings, package_settings)

        package_requests = self.baker.get_package_requests_from_settings(package_settings)
        self.assertEqual(self.package_requests, package_requests)

    def test_get_resolved_settings_from_package_requests(self):

        resolved_package_settings = self.baker.get_resolved_settings_from_package_requests(self.package_requests)
        for expected_setting, setting in zip(self.resolved_package_settings, resolved_package_settings):
            self.assertEqual(expected_setting.name, setting.name)
            self.assertEqual(expected_setting.value, setting.value)
            self.assertEqual(expected_setting.setting_type.launcher_type, setting.setting_type.launcher_type)

    def test_create_new_preset_from_package_settings(self):

        self.baker.create_new_preset_from_package_settings(self.new_preset_path, self.resolved_package_settings, 'test')

    def test_package_settings_not_found_in_source_preset(self):

        launcher_service = LauncherHessianService(StubPresetProxy(settings=self.preset_settings, preset_path=self.preset_path, preset=self.new_preset), StubToolsetProxy())
        rez_service = StubRezService(self.resolved_package_settings)
        self.baker = Baker(launcher_service, rez_service)
        self.assertRaises(BakerError, self.baker.bake, self.preset_path, self.new_preset_path)

    def test_package_settings_do_not_resolve(self):

        self.assertRaises(BakerError, self.baker.get_resolved_settings_from_package_requests, ['conflict', 'foo-1'])

