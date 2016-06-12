"""
Executes pre- and post-release shell commands
"""
from rez.release_hook import ReleaseHook
from rez.exceptions import ReleaseHookCancellingError
from rez.config import config
from rez.system import system
from rez.utils.logging_ import print_debug
from rez.utils.scope import scoped_formatter
from rez.utils.formatting import expandvars
from rez.vendor.schema.schema import Schema, Or, Optional, Use, And
from rez.vendor.sh.sh import Command, ErrorReturnCode, sudo, which
import getpass
import sys
import os


class CommandReleaseHook(ReleaseHook):

    commands_schema = Schema(
        {"command":     basestring,
         Optional("args"):  Or(And(basestring,
                                   Use(lambda x: x.strip().split())),
                               [basestring]),
         Optional("user"):  basestring,
         Optional("env"):   dict})

    schema_dict = {
        "print_commands":           bool,
        "print_output":             bool,
        "print_error":              bool,
        "cancel_on_error":          bool,
        "stop_on_error":            bool,
        "pre_build_commands":       [commands_schema],
        "pre_release_commands":     [commands_schema],
        "post_release_commands":    [commands_schema]}

    @classmethod
    def name(cls):
        return "command"

    def __init__(self, source_path):
        super(CommandReleaseHook, self).__init__(source_path)

    def execute_command(self, cmd_name, cmd_arguments, user, errors, env=None):
        def _err(msg):
            errors.append(msg)
            if self.settings.print_error:
                print >> sys.stderr, msg

        kwargs = {}
        if env:
            kwargs["_env"] = env

        def _execute(cmd, arguments):
            try:
                result = cmd(*(arguments or []), **kwargs)
                if self.settings.print_output:
                    print result.stdout.strip()
            except ErrorReturnCode as e:
                # `e` shows the command that was run
                msg = "command failed:\n%s" % str(e)
                _err(msg)
                return False
            return True

        if not os.path.isfile(cmd_name):
            cmd_full_path = which(cmd_name)
        else:
            cmd_full_path = cmd_name
        if not cmd_full_path:
            msg = "%s: command not found" % cmd_name
            _err(msg)
            return False

        run_cmd = Command(cmd_full_path)
        if user == 'root':
            with sudo:
                return _execute(run_cmd, cmd_arguments)
        elif user and user != getpass.getuser():
            raise NotImplementedError  # TODO
        else:
            return _execute(run_cmd, cmd_arguments)

    def pre_build(self, user, install_path, **kwargs):
        errors = []
        self._execute_commands(self.settings.pre_build_commands,
                               install_path=install_path,
                               package=self.package,
                               errors=errors)

        if errors and self.settings.cancel_on_error:
            raise ReleaseHookCancellingError(
                "The following pre-build commands failed:\n%s"
                % '\n\n'.join(errors))

    def pre_release(self, user, install_path, **kwargs):
        errors = []
        self._execute_commands(self.settings.pre_release_commands,
                               install_path=install_path,
                               package=self.package,
                               errors=errors)

        if errors and self.settings.cancel_on_error:
            raise ReleaseHookCancellingError(
                "The following pre-release commands failed:\n%s"
                % '\n\n'.join(errors))

    def post_release(self, user, install_path, variants, **kwargs):
        # note that the package we use here is the *installed* package, not the
        # developer package (self.package). Otherwise, attributes such as 'root'
        # will be None
        errors = []
        if variants:
            package = variants[0].parent
        else:
            package = self.package

        self._execute_commands(self.settings.post_release_commands,
                               install_path=install_path,
                               package=package,
                               errors=errors)
        if errors:
            print_debug("The following post-release commands failed:\n"
                        + '\n\n'.join(errors))

    def _execute_commands(self, commands, install_path, package, errors=None):
        release_dict = dict(path=install_path)
        formatter = scoped_formatter(system=system,
                                     release=release_dict,
                                     package=package)

        for conf in commands:
            program = conf["command"]

            env_ = None
            env = conf.get("env")
            if env:
                env_ = os.environ.copy()
                env_.update(env)

            args = conf.get("args", [])
            args = [formatter.format(x) for x in args]
            args = [expandvars(x, environ=env_) for x in args]

            if self.settings.print_commands or config.debug("package_release"):
                from subprocess import list2cmdline
                toks = [program] + args

                msgs = []
                msgs.append("running command: %s" % list2cmdline(toks))
                if env:
                    for key, value in env.iteritems():
                        msgs.append("    with: %s=%s" % (key, value))

                if self.settings.print_commands:
                    print '\n'.join(msgs)
                else:
                    for msg in msgs:
                        print_debug(msg)

            if not self.execute_command(cmd_name=program,
                                        cmd_arguments=args,
                                        user=conf.get("user"),
                                        errors=errors,
                                        env=env_):
                if self.settings.stop_on_error:
                    return


def register_plugin():
    return CommandReleaseHook


# Copyright 2016 Allan Johns.
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
