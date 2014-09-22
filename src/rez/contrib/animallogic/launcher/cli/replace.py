"""
Replace a launcher preset content with a different chunk .
"""
import getpass

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.setting import ValueSetting
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.config import config
from rez.vendor import argparse
import logging


logger = logging.getLogger(__name__)


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
    username = getpass.getuser()

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)

    references = launcher_service.get_references_from_path(destination, username)

    for reference in references:
        referencePath = launcher_service.get_preset_full_path(reference.get_preset_id(), None)
        logger.info('Removing reference %s from %s' % (referencePath, destination))
        launcher_service.remove_reference_from_path(destination, referencePath, username, description)

    logger.info('Adding %s reference to %s' % (newReference, destination))
    launcher_service.add_reference_to_preset_path(destination, newReference, username, description)

