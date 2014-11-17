"""
Bake a launcher preset based on the resolution of a rez environment.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service import LauncherHessianService
from rez.contrib.animallogic.launcher.resolver import RezService
from rez.contrib.animallogic.launcher.baker import Baker
from rez.contrib.animallogic.launcher.setting import ValueSetting
from rez.contrib.animallogic.launcher.settingtype import SettingType
from rez.contrib.animallogic.util import get_epoch_datetime_from_str
from rez.config import config
from rez.vendor import argparse
import logging
import sys


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
    parser.add_argument("--destination",
                        help="the destination preset in which to store the result. "
                             "If not provided the settings are printed to stdout.")
    parser.add_argument("--description",
                        help="a description for the new preset that is created.")
    parser.add_argument("--skip-resolve", default=False, action='store_true',
                        help="do not resolve packages found in the source setting."
                        "This will cause package and version settings to be baked as-is.")
    parser.add_argument("--preserve-system-settings", default=False, action='store_true',
                        help="this will preserve protected system settings provided"
                        "by Launcher.  This option is dangerous and should be used with caution.")
    parser.add_argument("--only-packages", default=False, action='store_true',
                        help="discard all settings apart from those of type package.")
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
    parser.add_argument("-t", "--time", type=str,
                        help="ignore packages released after the given time. "
                        "Supported formats are: epoch time (eg 1393014494), "
                        "relative time (eg -10s, -5m, -0.5h, -10d), or an"
                        "exact time (eg 'YYYY_mm_dd_HH_MM_SS').")


def command(opts, parser, extra_arg_groups=None):

    source = opts.source
    description = opts.description
    format = "%Y_%m_%d_%H_%M_%S"
    epoch = get_epoch_datetime_from_str(opts.time.strip(), format) if opts.time else None

    if not description:
        description = "Preset automatically baked by Rez from %s. The command used was %s" % (source, " ".join(sys.argv))

    bake(source, opts.destination, description, opts.overrides, opts.skip_resolve,
            opts.max_fails, opts.only_packages, epoch)


def bake(source, destination, description, overrides, skip_resolve,
            max_fails, only_packages, epoch):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    toolset_proxy = client.HessianProxy(config.launcher_service_url + "/toolset")

    launcher_service = LauncherHessianService(preset_proxy, toolset_proxy)
    rez_service = RezService()

    baker = Baker(launcher_service, rez_service, epoch=epoch)

    logger.info("Retrieving settings from Launcher %s." % source)
    baker.set_settings_from_launcher(source, preserve_system_settings=False)

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

    if destination:
        logger.info("Creating new preset %s from settings." % destination)
        baker.create_new_preset_from_settings(destination, description=description)
    else:
        print_settings(baker.settings)


def print_settings(settings):
    packages = []
    for setting in settings:
        separator = ''
        if setting.setting_type == SettingType.package:
            if not setting.value.startswith('=='):
                separator = '-'
            packages.append(setting.name + separator + str(setting.value))
            continue
        else:
            separator = '='
            print setting.name + separator + "'" + str(setting.value) + "'"

    print "REZ_PACKAGES_REQUEST='%s'" % ' '.join(packages)

def display_settings(settings):

    for setting in settings:
        logger.info("\t%7s %s=%s" % (setting.setting_type.name, setting.name, setting.value))

