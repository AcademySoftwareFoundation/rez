"""
Open a Launcher configured shell.
"""

from rez.config import config
from rez.contrib.animallogic.hessian import client
from rez.contrib.animallogic.launcher.service.hessian import LauncherHessianService
from rez.contrib.animallogic.launcher.model.mode import Mode
from rez.contrib.animallogic.launcher.model.operatingsystem import OperatingSystem
from rez.platform_ import platform_
from rez.shells import get_shell_types, create_shell
from rez.system import system
from rez.vendor import argparse
import datetime
import getpass
import logging
import os
import random
import sys


logger = logging.getLogger(__name__)


def setup_parser(parser):
    shells = get_shell_types()

    parser.add_argument("--detached", default=False, action='store_true',
                        help="open a separate terminal.")
    parser.add_argument("-c", "--command", default=None,
                        help="read commands from string. Alternatively, list command.")
    parser.add_argument("--shell", dest="shell", type=str, choices=shells,
                        default=system.shell,
                        help="target shell type (default: %(default)s)")
    parser.add_argument("preset", help="The preset to open.")


def command(opts, parser, extra_arg_groups=None):

    preset_proxy = client.HessianProxy(config.launcher_service_url + "/preset")
    preset_path = opts.preset
    command = opts.command
    detached = opts.detached
    username = getpass.getuser()
    mode = Mode.shell
    operating_system = OperatingSystem.get_current_operating_system()
    date = datetime.datetime.now()
    random_number = int(random.random() * 10**18) # random number the same length as used by Launcher
    script_file = os.path.join(config.tmpdir, "launch%d.py" % random_number)

    if not command:
        sh = create_shell(opts.shell)

        terminal_emulator_command = ""
        if detached:
            terminal_emulator_command = config.terminal_emulator_command
            if terminal_emulator_command:
                terminal_emulator_command = terminal_emulator_command.strip()
            else:
                terminal_emulator_command = " ".join(platform_.terminal_emulator_command)

        command = "os.system('%s %s')" % (terminal_emulator_command, sh.executable)

    launcher_service = LauncherHessianService(preset_proxy, None)
    executable, script = launcher_service.get_script_for_preset_path(preset_path, operating_system, command=command, username=username, date=date, mode=mode)

    if not executable:
        executable = config.launch_python_exe[platform_.name]

    with open(script_file, "w") as fd:
        fd.write(script)

    os.system("%s %s" % (executable, script_file))
