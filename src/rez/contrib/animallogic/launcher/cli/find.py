"""
Search for settings in a Launcher preset hierarchy.  This command is analogous
to the standard Linux 'find' command.
"""

from rez.config import config
from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.model.settingtype import SettingType
from rez.contrib.animallogic.launcher.model.mode import Mode
from rez.contrib.animallogic.launcher.model.preset import Preset
from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.vendor.version.version import VersionRange
import datetime
import getpass
import logging


logger = logging.getLogger(__name__)



def setup_parser(parser):
    setting_types = map(lambda x:x.name, SettingType)

    parser.add_argument("preset", default="/Rez/applications",
                        help="The preset to list.")
    parser.add_argument("--name",
                        help="find a setting with the specified name.")
    parser.add_argument("--value",
                        help="find a setting with the specified value.")
    parser.add_argument("--type", choices=setting_types,
                        help="find a setting with the specified type. available"
                        "types are ")
    parser.add_argument("-version",
                        help="find a setting whose value is within the given version range.")
    parser.add_argument("-f", "--format", default="{path}",
                        help="display the results using the provided format string.")


def command(opts, parser, extra_arg_groups=None):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    preset_path = opts.preset
    username = getpass.getuser()
    operating_system = OperatingSystem.get_current_operating_system()
    mode = Mode.shell
    find_name = opts.name
    find_type = SettingType[opts.type] if opts.type else None
    find_value = opts.value
    find_version = VersionRange(opts.version) if opts.version else None
    format_specification = opts.format
    date = datetime.datetime.now()

    launcher_service = LauncherHessianService(preset_proxy, None)
    root = launcher_service.resolve_preset_path(preset_path, date)[-1]

    for child in root.get_children(date, recursive=True):
        if isinstance(child, Preset):
            unresolved_settings = launcher_service.get_unresolved_settings_from_path(child.path, operating_system=operating_system, date=date)
            settings = launcher_service.resolve_settings(unresolved_settings)

            for setting in settings:
                if setting.parent_id is None:
                    continue

                try:
                    setting_version = VersionRange(setting.value)
                except:
                    setting_version = None

                match = True

                if find_type:
                    if setting.setting_type != find_type:
                        match = False

                if find_name:
                    if setting.name != find_name:
                        match = False

                if find_value:
                    if setting.value != find_value:
                        match = False

                if find_version:
                    if not setting_version:
                        match = False

                    elif not find_version.intersects(setting_version):
                        match = False

                if match:
                    print setting.format(format_specification)
