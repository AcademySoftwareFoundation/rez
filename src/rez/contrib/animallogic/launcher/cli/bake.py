"""
Bake a launcher preset based on the resolution of a rez environment.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.baker import Baker
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

    parser.add_argument("--source", required=True, 
                        help="the source preset/toolset to bake.")
    parser.add_argument("--destination", required=True, 
                        help="the destination preset in which to store the result.")
    parser.add_argument("--description", 
                        help="a description for the new preset that is created.")
    parser.add_argument("--skip-resolve", default=False, action='store_true',
                        help="do not resolve packages found in the source setting."
                        "This will cause package and version settings to be baked as-is.")
    parser.add_argument("--preserve-system-settings", default=False, action='store_true',
                        help="this will preserve protected system settings provided"
                        "by Launcher.  This option is dangerous and should be used with caution.")
    parser.add_argument("--only-packages", default=False, action='store_true',
                        help="discard all settings apare from those of type package.")
    parser.add_argument("--max-fails", type=int, default=-1, dest="max_fails",
                        metavar="N",
                        help="abort if the number of failed configuration attempts"
                        "exceeds N")
    parser.add_argument("--overrides", default=[], nargs='+', metavar='type:name=value', 
                        type=argparse_setting,
                        help='overrides that can be applied to the settings retrieved'
                        'from Launcher.  Each override must be of the form type:name=value'
                        'however if type is not specified the setting will be created'
                        'as type string.  Note these overrides apply *after* the settings'
                        'have been retrieved from Launcher, and not before.')


def command(opts, parser, extra_arg_groups=None):

    source = opts.source
    description = opts.description

    if not description:
        description = "Preset automatically baked by Rez from %s." % source

    bake(source, opts.destination, description, opts.overrides, opts.skip_resolve, 
            opts.max_fails, opts.preserve_system_settings, opts.only_packages)


def bake(source, destination, description, overrides, skip_resolve, 
            max_fails, preserve_system_settings, only_packages):

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

    if only_packages:
        logger.info("Removing non-package settings.")
        baker.filter_settings(lambda x: x.is_package_setting())

    if not skip_resolve:
        logger.info("Resolving package requests.")
        baker.resolve_package_settings(max_fails=max_fails, preserve_system_package_settings=False)

        logger.info("Resolved settings:")
        display_settings(baker.settings)

    logger.info("Creating new preset %s from settings." % destination)
    baker.create_new_preset_from_settings(destination, description=description)


def display_settings(settings):

    for setting in settings:
        logger.info("\t%7s %s=%s" % (setting.setting_type.name, setting.name, setting.value))

