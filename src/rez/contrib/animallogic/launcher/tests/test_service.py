from rez.contrib.animallogic.launcher.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.launcher.mode import Mode
from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy
import rez.vendor.unittest2 as unittest
import datetime

class TestLauncherHessianService(unittest.TestCase):

    def setUp(self):

        self.username = 'username'
        self.operating_system = OperatingSystem.get_current_operating_system()
        self.now = datetime.datetime.now()
        self.mode = Mode.shell

        self.new_preset = {'fullyQualifiedName':'/presets/Rez/test_new', 'description':'bar', 'parentId':{'key':43325883}, 'id':{'key':4077}, 'name':'test_new'}
        self.new_setting = Setting('new', 'value', SettingType.string)
        self.preset_settings = [{'name':'preset_setting', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 123, 'sourcePresetId':{'key':999}}]
        self.preset_path = '/presets/Rez/test'
        self.toolset_settings = [{'name':'preset_setting', 'value':'4.5.6', 'opSystem':{'name':'linux'}, 'type':{'name':'tVersion'}, 'id': 456, 'sourcePresetId':{'key':998}}]
        self.toolset_path = '/toolsets/Rez/test'

        self.launcher_service = LauncherHessianService(StubPresetProxy(self.preset_settings, self.new_preset), StubToolsetProxy(self.toolset_settings))

    def assert_preset(self, expected, preset):

        self.assertEqual(expected['name'], preset.name)
        self.assertEqual(expected['description'], preset.description)
        self.assertEqual(expected['parentId']['key'], preset.parent_id)
        self.assertEqual(expected['id']['key'], preset.id)

    def assert_setting(self, expected, setting):

        self.assertEqual(expected['name'], setting.name)
        self.assertEqual(expected['value'], setting.value)
        
        if expected['opSystem']:
            self.assertEqual(expected['opSystem']['name'], setting.operating_system.value)
        else:
            self.assertEqual(expected['opSystem'], setting.operating_system.value)

        self.assertEqual(expected['type']['name'], setting.setting_type.launcher_type)
        self.assertEqual(expected['id'], setting.id)
        self.assertEqual(expected['sourcePresetId']['key'], setting.source_preset_id)

    def assert_settings(self, expected_settings, settings):

        self.assertEqual(len(expected_settings), len(settings))
        for expected_setting, setting in zip(expected_settings, settings):
            self.assert_setting(expected_setting, setting)

    def test_get_settings_from_preset_path(self):

        settings = self.launcher_service.get_settings_from_path(self.preset_path, self.mode, username=self.username, operating_system=self.operating_system, date=self.now)
        self.assert_settings(self.preset_settings, settings)

    def test_get_settings_from_toolset_path(self):

        settings = self.launcher_service.get_settings_from_path(self.toolset_path, self.mode, username=self.username, operating_system=self.operating_system, date=self.now)
        self.assert_settings(self.toolset_settings, settings)

    def test_add_setting_to_preset(self):

        name, value, setting_type_as_dict = self.launcher_service.add_setting_to_preset(self.new_setting, self.preset_path, username=self.username)
        self.assertEqual(self.new_setting.name, name)
        self.assertEqual(self.new_setting.value, value)
        self.assertEqual({'name':self.new_setting.setting_type.launcher_type}, setting_type_as_dict)

    def test_create_preset(self):

        preset = self.launcher_service.create_preset(self.new_preset['fullyQualifiedName'], 'hello', username=self.username)
        self.assert_preset(self.new_preset, preset)
