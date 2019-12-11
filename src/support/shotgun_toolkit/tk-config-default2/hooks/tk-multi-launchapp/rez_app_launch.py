"""App Launch Hook - Rez.

Shotgun 8 hook to launch applications, potentially in a Rez context.

https://github.com/nerdvegas/rez

Rez packages can be requested via ``tk-multi-launchapp.yml``, as part of the
"extras" section and in a sub-section called "rez". Also, be sure to override
the default "hook_app_launch" with this hook: "rez_app_launch".

An example snippet from ``tk-multi-launchapp.yml`` for Maya...

.. code-block:: yaml

    settings.tk-multi-launchapp.maya:
      engine: tk-maya
      extra:
        rez:
          packages:
          - maya-2019
          - studio_maya_tools-1.2
          - show_maya_tools-dev
          parent_variables:
          - PYTHONPATH
          - MAYA_MODULE_PATH
          - MAYA_SCRIPT_PATH
      hook_app_launch: "{config}/tk-multi-launchapp/rez_app_launch.py"
      location: "@apps.tk-multi-launchapp.location"

    # maya
    settings.tk-multi-launchapp.maya:
      engine: tk-maya
      extra:
        rez:
          packages:
          - in_terminal
          - modremove
          - deadline
          - maya-2019
          - mtoa
          - maya_usd
          # -- Vendor Plugins/scripts --
          # CG
          - bifrost
          - pw_mGeoExporter-1.2
          # Python Modules
          - pyblish_base
          - pyblish_maya
          # -- WWFX packages (Always pick latest for new shells) --
          - animlembic_exporter
          - cometRename
          - image_resolutions
          parent_variables:
          - PYTHONPATH
          - MAYA_MODULE_PATH
          - MAYA_SCRIPT_PATH
      hook_app_launch: "{config}/tk-multi-launchapp/rez_app_launch.py"
      linux_path: "in-terminal --title 'Maya 2019 (Arnold LATEST)' maya"
      menu_name: "Maya 2019 (Arnold LATEST)"
      group: "Maya"
      group_default: true
      location: "@apps.tk-multi-launchapp.location"


Please note that this requires Rez to be installed as a package,
which exposes the Rez Python API. With a proper Rez installation, you can do
this by running ``rez-bind rez``.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import os
from pprint import pformat
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryFile

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class AppLaunch(HookBaseClass):
    """Hook to run an application."""

    def execute(self, app_path, app_args, version, **kwargs):
        """Start the required application using rez if required.

        Notes:
            - Define variables used to bootstrap tank from overwrite on
              first reference
            - Define others within ``tk-multi-launchapp.yml`` file in the
              ``extra:rez:parent_variables`` list.

        Args:
            app_path (str):
                The path of the application executable
            app_args (str):
                Any arguments the application may require
            version (str):
                version of the application being run if set in the "versions"
                settings of the Launcher instance, otherwise ``None``

        Returns:
            dict[str]:
                Execute results mapped to 'command' (str) and
                'return_code' (int).
        """
        multi_launchapp = self.parent
        rez_info = multi_launchapp.get_setting("extra", {}).get("rez", {})
        cmd, shell_type = self.background_cmd_shell_type(app_path, app_args)

        # Execute App in a Rez context
        rez_py_path = self.get_rez_path()
        if rez_py_path:
            if rez_py_path not in sys.path:
                self.logger.debug('Appending to sys.path: "%s"', rez_py_path)
                sys.path.append(rez_py_path)

            # Only import after rez_py_path is inside sys.path
            from rez.resolved_context import ResolvedContext
            from rez.config import config
            rez_parent_variables = rez_info.get("parent_variables", [])
            rez_packages = rez_info.get("packages", [])
            self.logger.debug("rez parent variables: %s", rez_parent_variables)
            self.logger.debug("rez packages: %s", rez_packages)

            config.parent_variables = rez_parent_variables
            context = ResolvedContext(rez_packages)
            current_env = os.environ.copy()

            env_kwargs = {'suffix': '-prev-env.py', 'delete': False}
            with NamedTemporaryFile(mode='w+', **env_kwargs) as env_file:
                env_file.write(pformat(current_env))
                self.logger.debug(
                    'Copied existing env for rez. See: "%s"',
                    env_file.name
                    )

            with TemporaryFile(mode='w+') as info_buffer:
                context.print_info(buf=info_buffer)
                info_buffer.seek(0)
                self.logger.debug(
                    "Executing in rez context [%s]: %s\n%s",
                    shell_type,
                    cmd,
                    info_buffer.read(),
                    )

            launcher_process = context.execute_shell(
                command=cmd,
                parent_environ=current_env,
                shell=shell_type,
                stdin=False,
                block=False
                )
            exit_code = launcher_process.wait()
        else:
            # run the command to launch the app
            exit_code = subprocess.check_call(cmd)

        return {"command": cmd, "return_code": exit_code}

    def background_cmd_shell_type(self, app_path, app_args):
        """Make command string and shell type name for current environment.

        Args:
            app_path (str): The path of the application executable.
            app_args (str): Any arguments the application may require.

        Returns:
            str, str: Command to run and (rez) shell type to run in.
        """
        system = sys.platform
        shell_type = 'bash'

        if system.startswith("linux"):
            # on linux, we just run the executable directly
            cmd_template = "{path} {flattened_args} &"

        elif self.parent.get_setting("engine") in ["tk-flame", "tk-flare"]:
            # flame and flare works in a different way from other DCCs
            # on both linux and mac, they run unix-style command line
            # and on the mac the more standardized "open" command cannot
            # be utilized.
            cmd_template = "{path} {flattened_args} &"

        elif system == "darwin":
            # on the mac, the executable paths are normally pointing
            # to the application bundle and not to the binary file
            # embedded in the bundle, meaning that we should use the
            # built-in mac open command to execute it
            cmd_template = 'open -n "{path}"'
            if app_args:
                app_args = app_args.replace('"', r'\"')
                cmd_template += ' --args "{flattened_args}"'

        elif system == "win32":
            # on windows, we run the start command in order to avoid
            # any command shells popping up as part of the application launch.
            cmd_template = 'start /B "App" "{path}" {flattened_args}'

        else:
            error = (
                'No cmd (formatting) and shell_type implemented for "%s":\n'
                '- app_path:"%s"\n'
                '- app_args:"%s"'
            )
            raise NotImplementedError(error % (system, app_path, app_args))

        cmd = cmd_template.format(path=app_path, flattened_args=app_args)
        return cmd, shell_type

    def get_rez_path(self, strict=True):
        """Get ``rez`` python package path from the current environment.

        Args:
            strict (bool):
                Whether to raise an error if Rez is not available as a package.
                This will prevent the app from being launched.

        Returns:
            str: A path to the Rez package, can be empty if ``strict=False``..
        """
        rez_cmd = "rez-python -c 'import rez; print(rez.__path__[0])'"
        process = subprocess.Popen(rez_cmd, stdout=subprocess.PIPE, shell=True)
        rez_python_path, err = process.communicate()

        if err or not rez_python_path:
            if strict:
                raise ImportError(
                    "Failed to find Rez as a package in the current "
                    "environment! Try 'rez-bind rez'!"
                    )
            else:
                self.logger.warn(
                    "Failed to find a Rez package in the current "
                    "environment. Unable to request Rez packages."
                    )

            rez_python_path = ""
        else:
            absolute_path = os.path.abspath(rez_python_path.strip())
            rez_python_path = os.path.dirname(absolute_path)
            self.logger.debug("Found Rez in: %s", rez_python_path)

        return rez_python_path


# Copyright 2013-2016 Allan Johns, Shotgun Software Inc.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
