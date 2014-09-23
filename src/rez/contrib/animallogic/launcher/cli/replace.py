"""
Replace a launcher preset references.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.replacer import Replacer
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.setting import ValueSetting
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.config import config
from rez.vendor import argparse

def argparse_setting(string):
    try:
        setting, value = string.split("=", 1)
        bits = setting.split(":", 1)

        name = bits[-1]
        setting_type = SettingType['string']
        if len(bits) == 2:
            setting_type = SettingType[bits[0]]

        return ValueSetting(name, value, setting_type)

    except:
        raise argparse.ArgumentTypeError("must be in the format type:name=value.")


def setup_parser(parser):

    parser.add_argument("--reference", required=True,
                        help="the reference launcher path to replace in the destination preset.")
    parser.add_argument("--destination", required=True,
                        help="the destination preset in which to change the reference.")
    parser.add_argument("--description", 
                        help="a description for the reference change.")

def command(opts, parser, extra_arg_groups=None):

    reference = opts.reference
    description = opts.description

    if not description:
        description = "Preset automatically updated from rez-launcher replace. Adding %s." % reference

    replace(reference, opts.destination, description)


def replace(newReference, destination, description):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")
    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)

    replacer = Replacer(launcher_service)

    replacer.replace(newReference, destination, description)

