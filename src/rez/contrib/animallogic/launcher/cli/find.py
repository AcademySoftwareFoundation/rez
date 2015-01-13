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

    parser.add_argument("preset", default="/Rez/applications",
                        help="The preset to list.")
    parser.add_argument("--name",
                        help="use a long listing format.")
    parser.add_argument("--value",
                        help="list submembers recursively.")
    parser.add_argument("--type",
                        help="list presets only.")
    parser.add_argument("-version",
                        help="this option is ignored when used with -l/--long.")
    parser.add_argument("-f", "--format", default="{path}",
                        help="this option is ignored when used with -l/--long.")


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
            settings = launcher_service.get_unresolved_settings_from_path(child.path, operating_system=operating_system, date=date)
            settings = launcher_service.resolve_settings(settings)

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
