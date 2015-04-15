from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.mode import Mode
from rez.contrib.animallogic.launcher.model.setting import ValueSetting, ReferenceSetting
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.service.hessian import SettingsResolver
from rez.contrib.animallogic.launcher.exceptions import LauncherError
from rez.contrib.animallogic.launcher.tests.stubs import StubPresetProxy, StubToolsetProxy
import rez.vendor.unittest2 as unittest
import datetime


class BaseTestLauncherHessianService(unittest.TestCase):

    def setUp(self):

        self.username = 'username'
        self.operating_system = OperatingSystem.get_current_operating_system()
        self.now = datetime.datetime.now()
        self.mode = Mode.shell

    def assert_settings(self, expected_settings, settings):

        self.assertEqual(len(expected_settings), len(settings))
        for expected_setting, setting in zip(expected_settings, settings):
            self.assert_setting(expected_setting, setting)

    def assert_setting(self, expected, setting):

        self.assertEqual(expected['name'], setting.name)
        self.assertEqual(expected['value'], setting.value)

        if expected['opSystem']:
            self.assertEqual(expected['opSystem']['name'], setting.operating_system.value)
        else:
            self.assertEqual(expected['opSystem'], setting.operating_system.value)

        self.assertEqual(expected['type']['name'], setting.setting_type.launcher_type)
        self.assertEqual(expected['id'], setting.id)
        self.assertEqual(expected['sourcePresetId']['key'], setting.parent_id)

    def assert_preset(self, expected, preset):

        self.assertEqual(expected['name'], preset.name)
        self.assertEqual(expected['description'], preset.description)
        self.assertEqual(expected['parentId']['key'], preset.parent_id)
        self.assertEqual(expected['id']['key'], preset.id)


class TestLauncherHessianService_GetSettings(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)

        self.preset_settings = [{'name':'preset_setting', 'value':'1.2.3', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 123, 'sourcePresetId':{'key':999}}]
        self.preset_path = '/presets/Rez/test'
        self.toolset_settings = [{'name':'preset_setting', 'value':'4.5.6', 'opSystem':{'name':'linux'}, 'type':{'name':'tVersion'}, 'id': 456, 'sourcePresetId':{'key':998}}]
        self.toolset_path = '/toolsets/Rez/test'

    def test_get_settings_from_preset_path(self):

        launcher_service = LauncherHessianService(StubPresetProxy(self.preset_settings, self.preset_path), StubToolsetProxy({}, ""))

        settings = launcher_service.get_settings_from_path(self.preset_path, self.mode, username=self.username, operating_system=self.operating_system, date=self.now)
        self.assert_settings(self.preset_settings, settings)

    def test_get_settings_from_toolset_path(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy(self.toolset_settings, self.toolset_path))

        settings = launcher_service.get_settings_from_path(self.toolset_path, self.mode, username=self.username, operating_system=self.operating_system, date=self.now)
        self.assert_settings(self.toolset_settings, settings)

    def test_get_settings_from_preset_path_that_does_not_exist(self):

        launcher_service = LauncherHessianService(StubPresetProxy(self.preset_settings, self.preset_path), StubToolsetProxy({}, ""))

        self.assertRaises(LauncherError, launcher_service.get_settings_from_path, "/presets/path/does/not/exist", self.mode, username=self.username, operating_system=self.operating_system, date=self.now)

    def test_get_settings_from_toolset_path_that_does_not_exist(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy(self.toolset_settings, self.toolset_path))

        self.assertRaises(LauncherError, launcher_service.get_settings_from_path, "/path/does/not/exist", self.mode, username=self.username, operating_system=self.operating_system, date=self.now)

    def test_get_unresolved_settings_from_path(self):

        preset_settings = [{'name':'preset_setting', 'value':'${abc}', 'opSystem':None, 'type':{'name':'tPackage'}, 'id': 123, 'sourcePresetId':{'key':999}}]
        preset_path = '/presets/Rez/test'
        toolset_settings = [{'name':'toolset_setting', 'value':'${abc}', 'opSystem':{'name':'linux'}, 'type':{'name':'tVersion'}, 'id': 456, 'sourcePresetId':{'key':998}}]
        toolset_path = '/toolsets/Rez/test'

        launcher_service = LauncherHessianService(StubPresetProxy(preset_settings, preset_path), StubToolsetProxy(toolset_settings, toolset_path))

        settings = launcher_service.get_unresolved_settings_from_path(preset_path, operating_system=self.operating_system, date=self.now)
        self.assert_settings(preset_settings, settings)

        self.assertRaises(LauncherError, launcher_service.get_unresolved_settings_from_path, toolset_path, operating_system=self.operating_system, date=self.now)


class TestLauncherHessianService_AddSettingToPreset(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)

        self.new_setting = ValueSetting(None, None, 'new', 'value', SettingType.string, None)

    def test_add_setting_to_preset(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))

        name, value, setting_type_as_dict = launcher_service.add_setting_to_preset(self.new_setting, "/preset/path", username=self.username)
        self.assertEqual(self.new_setting.name, name)
        self.assertEqual(self.new_setting.value, value)
        self.assertEqual({'name':self.new_setting.setting_type.launcher_type}, setting_type_as_dict)

    def test_add_settings_to_preset(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))

        settings = launcher_service.add_settings_to_preset([self.new_setting], "/preset/path", self.username)
        self.assertEqual(self.new_setting.name, settings[0]["name"])
        self.assertEqual(self.new_setting.value, settings[0]["value"])
        self.assertEqual({'name':self.new_setting.setting_type.launcher_type}, settings[0]["type"])


class TestLauncherHessianService_CreatePreset(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)

        self.new_preset = {'fullyQualifiedName':'/presets/Rez/test_new', 'description':'bar', 'parentId':{'key':43325883}, 'id':{'key':4077}, 'name':'test_new', 'version':1, 'createdBy':'unknown', 'createdOn':1421124354320}

    def test_create_preset(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, "", self.new_preset), StubToolsetProxy({}, ""))

        preset = launcher_service.create_preset(self.new_preset['fullyQualifiedName'], 'hello', username=self.username)
        self.assert_preset(self.new_preset, preset)


class TestLauncherHessianService_GetReferenceFromPreset(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)
        self.launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))
        self.reference_settings = [ReferenceSetting(1, None, 'Test', 1234), ReferenceSetting(2, None, 'base', 9999)]

    def test_get_reference_setting_from_preset(self):

        retrievedSettings = self.launcher_service.get_references_from_path("/presets/root/path")

        for retrievedRefSetting, referenceSetting in zip(retrievedSettings, self.reference_settings):
            self.assertEqual(retrievedRefSetting.name, referenceSetting.name)
            self.assertEqual(retrievedRefSetting.id, referenceSetting.id)
            self.assertEqual(retrievedRefSetting.preset_id, referenceSetting.preset_id)

    def test_get_reference_setting_for_wrong_path(self):

        self.assertRaises(Exception, self.launcher_service.get_references_from_path, "/a/wrong/preset/path")


class TestLauncherHessianService_GetPresetFullPath(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)
        self.launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))
        self.known_presets_ids = {'/test/full/path':  {u'key': 1234}, '/test/to/different/path/': {u'key': 9999}}
        self.unknown_presets_ids = {'/test/bla':  {u'key': 5555}, '/test/foo': {u'key': 4321}}

    def test_get_presets_full_path(self):

        for fullPresetPath, id, in self.known_presets_ids.iteritems():
            self.assertEqual(self.launcher_service.get_preset_full_path(id['key']), fullPresetPath)

    def test_get_presets_full_path_for_unknown_preset(self):
        for fullPresetPath, id, in self.unknown_presets_ids.iteritems():
            self.assertRaises(Exception, self.launcher_service.get_preset_full_path, id)


class TestLauncherHessianService_AddReferenceToPreset(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)
        self.launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))
        self.new_reference_setting = ReferenceSetting(None, None, '/test/full/path', 1234)

    def test_add_reference_setting_to_preset(self):

        refSetting = self.launcher_service.add_reference_to_preset_path("/presets/root/path", '/test/full/path',
                                                                        username=self.username)
        self.assertEqual(self.new_reference_setting.name, refSetting.name)
        self.assertEqual(self.new_reference_setting.preset_id, refSetting.preset_id)

    def test_add_reference_setting_with_preset_path(self):

        refSetting = self.launcher_service.add_reference_to_preset_path("/presets/root/path", '/presets/test/full/path',
                                                                        username=self.username)
        self.assertEqual(self.new_reference_setting.name, refSetting.name)
        self.assertEqual(self.new_reference_setting.preset_id, refSetting.preset_id)

    def test_add_bad_reference_setting_to_preset(self):

        launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))

        self.assertRaises(Exception, launcher_service.add_reference_to_preset_path, "/presets/root/path",
                          '/nonexistent/preset/path', username=self.username)


class TestLauncherHessianService_RemoveReferenceToPreset(BaseTestLauncherHessianService):

    def setUp(self):

        BaseTestLauncherHessianService.setUp(self)
        self.launcher_service = LauncherHessianService(StubPresetProxy({}, ""), StubToolsetProxy({}, ""))
        self.new_reference_setting = ReferenceSetting(None, None, '/test/full/path', 1234)

    def test_remove_reference_setting_to_preset(self):

        refSetting = self.launcher_service.remove_reference_from_path("/presets/root/path", '/test/full/path',
                                                                      username=self.username)
        self.assertEqual(self.new_reference_setting.name, refSetting.name)
        self.assertEqual(self.new_reference_setting.preset_id, refSetting.preset_id)

    def test_remove_reference_setting_with_preset_path(self):

        refSetting = self.launcher_service.remove_reference_from_path("/presets/root/path", '/presets/test/full/path',
                                                                      username=self.username)
        self.assertEqual(self.new_reference_setting.name, refSetting.name)
        self.assertEqual(self.new_reference_setting.preset_id, refSetting.preset_id)

    def test_add_bad_reference_setting_to_preset(self):

        self.assertRaises(Exception, self.launcher_service.remove_reference_from_path, "/presets/root/path",
                          '/nonexistent/preset/path', username=self.username)


class TestSettingsResolver(unittest.TestCase):

    def setUp(self):
        self.settings_resolver = SettingsResolver()

    def assertSettings(self, expected_settings, actual_settings):
        for expected, actual in zip(expected_settings, actual_settings):
            self.assertEqual(expected.name, actual.name)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.setting_type, actual.setting_type)

    def test_empty_settings_list(self):
        self.assertEqual([], self.settings_resolver.resolve_settings([]))

    def test_setting_without_reference(self):
        setting = ValueSetting(None, None, "name", "value", SettingType.string, None)

        resolved_settings = self.settings_resolver.resolve_settings([setting])
        self.assertSettings([setting], resolved_settings)

    def test_setting_with_undefined_reference(self):
        setting = ValueSetting(None, None, "name", "${value}", SettingType.string, None)

        resolved_settings = self.settings_resolver.resolve_settings([setting])
        self.assertSettings([setting], resolved_settings)

        setting = ValueSetting(None, None, "name", "pre ${value} post", SettingType.string, None)

        resolved_settings = self.settings_resolver.resolve_settings([setting])
        self.assertSettings([setting], resolved_settings)

    def test_settings_with_simple_self_reference(self):
        settings = [
                    ValueSetting(None, None, "name", "value", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name}", SettingType.string, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value", SettingType.string, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

        settings = [
                    ValueSetting(None, None, "name", "${name}", SettingType.string, None),
                    ValueSetting(None, None, "name", "value", SettingType.string, None),
                    ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_prepend_self_reference(self):
        settings = [
                    ValueSetting(None, None, "name", "${name}value1", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name}value2", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name}value3", SettingType.string, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value1value2value3", SettingType.string, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_overwrite_self_reference(self):
        settings = [
                    ValueSetting(None, None, "name", "${name}value1", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name}value2", SettingType.string, None),
                    ValueSetting(None, None, "name", "value3", SettingType.string, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value3", SettingType.string, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_reference_and_self_reference(self):
        settings = [
                    ValueSetting(None, None, "name", "value1", SettingType.string, None),
                    ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name} bar ${spam}", SettingType.string, None),
                    ValueSetting(None, None, "package", "${name}", SettingType.package, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value1 bar ham", SettingType.string, None),
                             ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                             ValueSetting(None, None, "package", "value1 bar ham", SettingType.package, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_reference_and_self_reference_only_packages(self):
        settings = [
                    ValueSetting(None, None, "name", "value1", SettingType.string, None),
                    ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name} bar ${spam}", SettingType.string, None),
                    ValueSetting(None, None, "package", "${name}", SettingType.package, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value1 bar ${spam}", SettingType.string, None),
                             ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                             ValueSetting(None, None, "package", "value1 bar ham", SettingType.package, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings, only_packages=True)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_nested_references(self):
        settings = [
                    ValueSetting(None, None, "name", "value1", SettingType.string, None),
                    ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                    ValueSetting(None, None, "eggs", "${spam}", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name} bar ${eggs}", SettingType.string, None),
                    ValueSetting(None, None, "package", "${name}", SettingType.package, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value1 bar ham", SettingType.string, None),
                             ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                             ValueSetting(None, None, "eggs", "ham", SettingType.string, None),
                             ValueSetting(None, None, "package", "value1 bar ham", SettingType.package, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_nested_references_only_packages(self):
        settings = [
                    ValueSetting(None, None, "name", "value1", SettingType.string, None),
                    ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                    ValueSetting(None, None, "eggs", "${spam}", SettingType.string, None),
                    ValueSetting(None, None, "name", "${name} bar ${eggs}", SettingType.string, None),
                    ValueSetting(None, None, "package", "${name}", SettingType.package, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "name", "value1 bar ${eggs}", SettingType.string, None),
                             ValueSetting(None, None, "spam", "ham", SettingType.string, None),
                             ValueSetting(None, None, "eggs", "${spam}", SettingType.string, None),
                             ValueSetting(None, None, "package", "value1 bar ham", SettingType.package, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings, only_packages=True)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_mixed_references(self):
        settings = [
                    ValueSetting(None, None, "a", "${path}:/tmp", SettingType.string, None),
                    ValueSetting(None, None, "path", "/var/tmp:${path}:/scratch", SettingType.string, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "a", "/var/tmp::/scratch:/tmp", SettingType.string, None),
                             ValueSetting(None, None, "path", "/var/tmp::/scratch", SettingType.string, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings)
        self.assertSettings(expected_settings, resolved_settings)

    def test_settings_with_mixed_references_only_packages(self):
        settings = [
                    ValueSetting(None, None, "a", "${path}:/tmp", SettingType.string, None),
                    ValueSetting(None, None, "path", "/var/tmp:${path}:/scratch", SettingType.string, None),
                    ]

        expected_settings = [
                             ValueSetting(None, None, "a", "${path}:/tmp", SettingType.string, None),
                             ValueSetting(None, None, "path", "/var/tmp::/scratch", SettingType.string, None),
                             ]

        resolved_settings = self.settings_resolver.resolve_settings(settings, only_packages=True)
        self.assertSettings(expected_settings, resolved_settings)
