from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.setting import ValueSetting
from rez.vendor import argparse

def argparse_setting(string):
    try:
        setting, value = string.split("=", 1)
        bits = setting.split(":", 1)

        name = bits[-1]
        setting_type = SettingType['string']
        if len(bits) == 2:
            setting_type = SettingType[bits[0]]

        return ValueSetting(None, None, name, value, setting_type, None)

    except:
        raise argparse.ArgumentTypeError("must be in the format type:name=value.")
