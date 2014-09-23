from rez.contrib.animallogic.launcher.setting import ValueSetting
from rez.contrib.animallogic.launcher.setting import ReferenceSetting
from rez.contrib.animallogic.launcher.settingtype import SettingType
import rez.vendor.unittest2 as unittest

class TestSetting(unittest.TestCase):

    def test_setting_as_package_request_with_value(self):

        name = 'foo'
        value = '1.0.0+'
        expected = name + '-' + value

        setting = ValueSetting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_without_value(self):

        name = 'foo'
        value = ''
        expected = name

        setting = ValueSetting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

        value = None

        setting = ValueSetting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_of_wrong_type(self):

        setting = ValueSetting('foo', '1.0.0+', SettingType.string)
        self.assertEqual(None, setting.get_setting_as_package_request())

    def test_reference_setting(self):

        name = 'bla'
        preset_id = 1234
        preset_id_dict = {u'key': 1234}

        refSetting = ReferenceSetting(name, preset_id)
        self.assertEqual(refSetting.get_preset_id_as_dict(), preset_id_dict)

