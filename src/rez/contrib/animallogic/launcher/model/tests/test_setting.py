from rez.contrib.animallogic.launcher.model.setting import ValueSetting
from rez.contrib.animallogic.launcher.model.setting import ReferenceSetting
from rez.contrib.animallogic.launcher.model.settingtype import SettingType
import rez.vendor.unittest2 as unittest

class TestSetting(unittest.TestCase):

    def test_setting_as_package_request_with_value(self):

        name = 'foo'
        value = '1.0.0+'
        expected = name + '-' + value

        setting = ValueSetting(None, None, name, value, SettingType.package, None)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_without_value(self):

        name = 'foo'
        value = ''
        expected = name

        setting = ValueSetting(None, None, name, value, SettingType.package, None)
        self.assertEqual(expected, setting.get_setting_as_package_request())

        value = None

        setting = ValueSetting(None, None, name, value, SettingType.package, None)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_of_wrong_type(self):

        setting = ValueSetting(None, None, 'foo', '1.0.0+', SettingType.string, None)
        self.assertEqual(None, setting.get_setting_as_package_request())

    def test_reference_setting(self):

        name = 'bla'
        preset_id = 1234

        refSetting = ReferenceSetting(None, None, name, preset_id)
        self.assertEqual(refSetting.preset_id, preset_id)

