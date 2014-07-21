from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.settingtype import SettingType
import rez.vendor.unittest2 as unittest

class TestSetting(unittest.TestCase):

    def test_setting_as_package_request_with_value(self):

        name = 'foo'
        value = '1.0.0+'
        expected = name + '-' + value

        setting = Setting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_without_value(self):

        name = 'foo'
        value = ''
        expected = name

        setting = Setting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

        value = None

        setting = Setting(name, value, SettingType.package)
        self.assertEqual(expected, setting.get_setting_as_package_request())

    def test_setting_as_package_request_of_wrong_type(self):

        setting = Setting('foo', '1.0.0+', SettingType.string)
        self.assertEqual(None, setting.get_setting_as_package_request())
