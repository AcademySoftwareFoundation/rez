"""
Bake a launcher preset based on the resolution of a rez environment.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.setting import Setting
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.config import config
from rez.vendor import argparse
import logging


logger = logging.getLogger(__name__)


def setup_parser(parser):

    def argparse_setting_type(string):
        try:
            name, value = string.split("=")
            return Setting(name, value, SettingType.string)
        except:
            raise argparse.ArgumentTypeError("must be in the format name=value.")

    parser.add_argument("--source", required=True, 
                        help="the source preset/toolset to bake.")
    parser.add_argument("--destination", required=True, 
                        help="the destination preset in which to store the result.")
    parser.add_argument("--description", 
                        help="a description for the new preset that is created.")
    parser.add_argument("--resolve-packages", default=False, action='store_true',
                        help="resolve packages found in the source setting.  This"
                        "will also remove all version settings from the resulting preset.")
    parser.add_argument("--preserve-system-settings", default=False, action='store_true',
                        help="this will preserve protected system settings provided"
                        "by Launcher.  This option is dangerous and should be used with caution.")
    parser.add_argument("--max-fails", type=int, default=-1, dest="max_fails",
                        metavar="N",
                        help="Abort if the number of failed configuration "
                        "attempts exceeds N")
    parser.add_argument("--overrides", default=[], nargs='+', metavar='name=value', 
                        type=argparse_setting_type,
                        help='overrides that can be applied to the settings retrieved'
                        'from Launcher.  Each override must be of the form name=value'
                        'and all settings will be created as type string.')


def command(opts, parser):

    bake(opts.source, opts.destination, opts.description, opts.overrides, opts.resolve_packages, opts.max_fails, opts.preserve_system_settings)


def bake(source, destination, description, overrides, resolve_packages, max_fails, preserve_system_settings):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)
    rez_service = RezService()

    baker = Baker(launcher_service, rez_service)

    logger.info("Retrieving settings from Launcher %s." % source)
    baker.set_settings_from_launcher(source, preserve_system_settings=preserve_system_settings)

    logger.info("Found settings:")
    display_settings(baker.settings)

    if overrides:
        logger.info("Applying overrides.")
        display_settings(overrides)
        baker.apply_overrides(overrides)

    if resolve_packages:
        logger.info("Resolving package requests.")
        baker.resolve_package_settings(max_fails=max_fails)

        logger.info("Resolved settings:")
        display_settings(baker.settings)

    logger.info("Creating new preset %s from settings." % destination)
    baker.create_new_preset_from_settings(destination, description=description)


def display_settings(settings):

    for setting in settings:
        logger.info("\t%7s %s=%s" % (setting.setting_type.name, setting.name, setting.value))

