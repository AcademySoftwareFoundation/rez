from rez.contrib.animallogic.launcher.model.settingtype import SettingType
import rez.vendor.unittest2 as unittest

class TestSettingType(unittest.TestCase):

    def test_create_from_launcher_type(self):

        setting_type = SettingType.create_from_launcher_type('tFloat')
        expected = SettingType.float

        self.assertEqual(expected, setting_type)

    def test_create_from_invalid_launcher_type(self):

        self.assertRaises(RuntimeError, SettingType.create_from_launcher_type, 'tInvalid')
