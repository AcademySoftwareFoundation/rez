from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.mode import Mode
from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.exceptions import BakerError, RezResolverError
from rez.contrib.animallogic.launcher.cli.bake import argparse_setting
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy, StubRezService
from rez.vendor import argparse
import rez.vendor.unittest2 as unittest


class TestBakerCLI(unittest.TestCase):

    def assert_setting(self, expected_name, expected_value, expected_setting_type, actual_setting):

        self.assertEqual(expected_name, actual_setting.name)
        self.assertEqual(expected_value, actual_setting.value)
        self.assertEqual(expected_setting_type, actual_setting.setting_type)

    def test_argparse_setting_with_type(self):

        setting = argparse_setting("string:FOO=BAR")
        self.assert_setting("FOO", "BAR", SettingType.string, setting)

        setting = argparse_setting("package:FOO=BAR")
        self.assert_setting("FOO", "BAR", SettingType.package, setting)

    def test_argparse_setting_with_invalid_type(self):

        self.assertRaises(argparse.ArgumentTypeError, argparse_setting, "invalid:FOO=BAR")

    def test_argparse_setting_without_type(self):

        setting = argparse_setting("FOO=BAR")
        self.assert_setting("FOO", "BAR", SettingType.string, setting)


class TestBaker(unittest.TestCase):

    def setUp(self):

        self.package_preset_settings = [
                                        {'name':'package_1', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 1, 'sourcePresetId':{'key':999}},
                                        {'name':'package_2', 'value':'', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 2, 'sourcePresetId':{'key':999}},
                                        {'name':'platform', 'value':'CentOS', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                       ]

        self.preset_settings = [
                                {'name':'string', 'value':'Hello, World!', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                {'name':'int', 'value':123, 'opSystem':None, 'type':{'name':'tInt'}, 'id': 4, 'sourcePresetId':{'key':999}},
                               ]

        self.system_settings = [
                                {'name':'AL_LAUNCHER_MODE', 'value':'shell', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                               ]

        self.override_settings = [
                                  {'name':'string', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                  {'name':'override_2', 'value':'2.0.1', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                 ]

        self.merged_override_settings = [
                                         {'name':'package_1', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 1, 'sourcePresetId':{'key':999}},
                                         {'name':'package_2', 'value':'', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 2, 'sourcePresetId':{'key':999}},
                                         {'name':'platform', 'value':'CentOS', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 2, 'sourcePresetId':{'key':999}},
                                         {'name':'string', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                         {'name':'int', 'value':123, 'opSystem':None, 'type':{'name':'tInt'}, 'id': 4, 'sourcePresetId':{'key':999}},
                                         {'name':'override_2', 'value':'2.0.1', 'opSystem':None, 'type':{'name':'tString'}, 'id': 3, 'sourcePresetId':{'key':999}},
                                        ]

        self.settings = self.package_preset_settings + self.preset_settings + self.system_settings
        self.preset_path = '/presets/Rez/test'
        self.new_preset_path = '/presets/Rez/test_new'
        self.new_preset = {'fullyQualifiedName':'/presets/Rez/test_new', 'description':'bar', 'parentId':{'key':43325883}, 'id':{'key':4077}, 'name':'test_new'}
        self.package_requests = ['package_1-1.2.3', 'package_2', 'platform-CentOS']
        self.resolved_package_settings = [Setting('package_1', '1.2.3', SettingType.package), Setting('package_2', '2.0.1', SettingType.package), Setting('platform', 'CentOS', SettingType.package)]
        self.overrides = [Setting('string', '1.2.3', SettingType.string), Setting('override_2', '2.0.1', SettingType.string)]

        launcher_service = LauncherHessianService(StubPresetProxy(settings=self.settings, preset_path=self.preset_path, preset=self.new_preset), StubToolsetProxy())
        rez_service = StubRezService(self.resolved_package_settings)
        self.baker = Baker(launcher_service, rez_service)

    def assert_setting(self, expected, setting):

        self.assertEqual(expected['name'], setting.name)
        self.assertEqual(expected['value'], setting.value)
        self.assertEqual(expected['type']['name'], setting.setting_type.launcher_type)

    def assert_settings(self, expected_settings, settings):

        self.assertEqual(len(expected_settings), len(settings))
        for expected_setting, setting in zip(expected_settings, settings):
            self.assert_setting(expected_setting, setting)

    def test_set_settings_from_launcher(self):

        self.baker.set_settings_from_launcher(self.preset_path, preserve_system_settings=False)
        self.assert_settings(self.package_preset_settings + self.preset_settings, self.baker.settings)

    def test_set_settings_from_launcher_preserve_system_settings(self):

        self.baker.set_settings_from_launcher(self.preset_path, preserve_system_settings=True)
        self.assert_settings(self.settings, self.baker.settings)

    def test_apply_overrides_without_original_settings(self):

        self.baker.apply_overrides(self.overrides)
        self.assert_settings(self.override_settings, self.baker.settings)

    def test_apply_overrides_with_original_settings(self):

        self.baker.set_settings_from_launcher(self.preset_path)
        self.baker.apply_overrides(self.overrides)
        self.assert_settings(self.merged_override_settings, self.baker.settings)

    def test_package_settings_do_not_resolve(self):

        self.baker.settings = [Setting('conflict', '', SettingType.package), Setting('foo', '1', SettingType.package)]
        self.assertRaises(BakerError, self.baker.resolve_package_settings)

    def test_filter_settings(self):

        self.baker.settings = self.resolved_package_settings
        self.baker.filter_settings(lambda x : not x.is_package_setting())
        self.assertEqual(len(self.baker.settings), 0)

    def test_resolve_package_settings(self):

        self.baker.set_settings_from_launcher(self.preset_path, preserve_system_settings=False)
        self.baker.resolve_package_settings()

        for setting in self.baker.settings:
            self.assertFalse(setting.is_system_package_setting())

    def test_resolve_package_settings_preserve_system_settings(self):

        self.baker.set_settings_from_launcher(self.preset_path, preserve_system_settings=False)
        self.baker.resolve_package_settings(preserve_system_package_settings=True)

        for setting in self.baker.settings:
            if setting.is_system_package_setting():
                break
        else:
            self.fail("System packages should not have been preserved.")
