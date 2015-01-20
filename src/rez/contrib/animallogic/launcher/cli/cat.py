"""
Concatenate Launcher presets and print on the standard output.  This command is
analogous to the standard Linux 'cat' command.
"""

from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.model.mode import Mode
from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.config import config
from rez.vendor import argparse
import datetime
import getpass
import logging
import sys


logger = logging.getLogger(__name__)


def setup_parser(parser):

    parser.add_argument("preset", help="The preset to print on the standard output.")


def command(opts, parser, extra_arg_groups=None):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    preset_path = opts.preset
    username = getpass.getuser()
    mode = Mode.shell
    operating_system = OperatingSystem.get_current_operating_system()
    date = datetime.datetime.now()

    launcher_service = LauncherHessianService(preset_proxy, None)
    _, script = launcher_service.get_script_for_preset_path(preset_path, operating_system, command=None, username=username, date=date, mode=mode)

    print script
