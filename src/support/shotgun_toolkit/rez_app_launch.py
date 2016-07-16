"""
App Launch Hook - Rez

This hook is executed to launch applications, potentially in a Rez context.

https://github.com/nerdvegas/rez

Rez packages can be requested via app_launchers.yml,
as part of the "extras" section and in a key called "rez_packages". Also be sure
to override the default "hook_app_launch" with this hook, "rez_app_launch".

An example snippet from app_launchers.yml for Maya...
    launch_maya:
      engine: tk-maya
      extra:
        rez_packages:
          - cool_rez_package
          - sweet_rez_package-1.2
      hook_app_launch: rez_app_launch

Please note that this requires Rez to be installed as a package,
which exposes the Rez Python API. With a proper Rez installation, you can do this
by running "rez-bind rez".
"""

import os
import sys
import subprocess
import tank


class AppLaunch(tank.Hook):
    """
    Hook to run an application.
    """

    def execute(self, app_path, app_args, version, **kwargs):
        """
        The execute functon of the hook will be called to start the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the "versions" settings
                              of the Launcher instance, otherwise None

        :returns: (dict) The two valid keys are 'command' (str) and 'return_code' (int).
        """

        multi_launchapp = self.parent
        extra = multi_launchapp.get_setting("extra")

        use_rez = False
        if self.check_rez():
            from rez.resolved_context import ResolvedContext
            from rez.config import config

            # Define variables used to bootstrap tank from overwrite on first reference
            # PYTHONPATH is used by tk-maya
            # NUKE_PATH is used by tk-nuke
            # HIERO_PLUGIN_PATH is used by tk-nuke (nukestudio)
            # KATANA_RESOURCES is used by tk-katana
            config.parent_variables = ["PYTHONPATH", "HOUDINI_PATH", "NUKE_PATH", "HIERO_PLUGIN_PATH", "KATANA_RESOURCES"]

            rez_packages = extra["rez_packages"]
            context = ResolvedContext(rez_packages)

            use_rez = True

        system = sys.platform
        shell_type = 'bash'
        if system == "linux2":
            # on linux, we just run the executable directly
            cmd = "%s %s &" % (app_path, app_args)

        elif self.parent.get_setting("engine") in ["tk-flame", "tk-flare"]:
            # flame and flare works in a different way from other DCCs
            # on both linux and mac, they run unix-style command line
            # and on the mac the more standardized "open" command cannot
            # be utilized.
            cmd = "%s %s &" % (app_path, app_args)

        elif system == "darwin":
            # on the mac, the executable paths are normally pointing
            # to the application bundle and not to the binary file
            # embedded in the bundle, meaning that we should use the
            # built-in mac open command to execute it
            cmd = "open -n \"%s\"" % (app_path)
            if app_args:
                cmd += " --args \"%s\"" % app_args.replace("\"", "\\\"")

        elif system == "win32":
            # on windows, we run the start command in order to avoid
            # any command shells popping up as part of the application launch.
            cmd = "start /B \"App\" \"%s\" %s" % (app_path, app_args)
            shell_type = 'cmd'

        # Execute App in a Rez context
        if use_rez:
            n_env = os.environ.copy()
            proc = context.execute_shell(
                command=cmd,
                parent_environ=n_env,
                shell=shell_type,
                stdin=False,
                block=False
            )
            exit_code = proc.wait()
            context.print_info(verbosity=True)

        else:
            # run the command to launch the app
            exit_code = os.system(cmd)

        return {
            "command": cmd,
            "return_code": exit_code
        }

    def check_rez(self, strict=True):
        """
        Checks to see if a Rez package is available in the current environment.
        If it is available, add it to the system path, exposing the Rez Python API

        :param strict: (bool) If True, raise an error if Rez is not available as a package.
                              This will prevent the app from being launched.

        :returns: A path to the Rez package.
        """

        system = sys.platform

        if system == "win32":
            rez_cmd = 'rez-env rez -- echo %REZ_REZ_ROOT%'
        else:
            rez_cmd = 'rez-env rez -- printenv REZ_REZ_ROOT'

        process = subprocess.Popen(rez_cmd, stdout=subprocess.PIPE, shell=True)
        rez_path, err = process.communicate()

        if err or not rez_path:
            if strict:
                raise ImportError("Failed to find Rez as a package in the current "
                                  "environment! Try 'rez-bind rez'!")
            else:
                print >> sys.stderr, ("WARNING: Failed to find a Rez package in the current "
                                      "environment. Unable to request Rez packages.")

            rez_path = ""
        else:
            rez_path = rez_path.strip()
            print "Found Rez:", rez_path
            print "Adding Rez to system path..."
            sys.path.append(rez_path)

        return rez_path


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
