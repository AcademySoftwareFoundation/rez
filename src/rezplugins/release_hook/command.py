"""
Executes pre- and post-release shell commands
"""
from rez.release_hook import ReleaseHook
from rez.exceptions import ReleaseError
from rez.config import config
from rez.util import print_debug
from rez.vendor.schema.schema import Schema, Or, Optional, Use, And
from rez.vendor.sh.sh import Command, ErrorReturnCode, sudo, which
import getpass
import sys
import os


class CommandReleaseHook(ReleaseHook):

    commands_schema = Schema(
        {"command":        basestring,
         Optional("args"):  Or(And(basestring,
                                   Use(lambda x: x.strip().split())),
                               [basestring]),
         Optional("user"):  basestring})

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
        self.settings = self.package.config.plugins.release_hook.command

    def execute_command(self, cmd_name, cmd_arguments, user, errors):
        def _err(msg):
            errors.append(msg)
            if self.settings.print_error:
                print >> sys.stderr, msg

        def _execute(cmd, arguments):
            try:
                result = cmd(*(arguments or []))
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

    def _release(self, commands, errors=None):
        for conf in commands:
            if self.settings.print_commands or config.debug("package_release"):
                from subprocess import list2cmdline
                toks = [conf["command"]] + conf.get("args", [])
                msg = "running command: %s" % list2cmdline(toks)
                if self.settings.print_commands:
                    print msg
                else:
                    print_debug(msg)

            if not self.execute_command(cmd_name=conf.get("command"),
                                        cmd_arguments=conf.get("args"),
                                        user=conf.get("user"),
                                        errors=errors):
                if self.settings.stop_on_error:
                    return

    def pre_build(self, user, install_path, release_message=None,
                  changelog=None, previous_version=None,
                  previous_revision=None):
        errors = []
        self._release(self.settings.pre_build_commands, errors=errors)
        if errors and self.settings.cancel_on_error:
            raise ReleaseError("The release was cancelled due to the "
                               "following failed pre-build commands:\n%s"
                               % '\n\n'.join(errors))

    def pre_release(self, user, install_path, release_message=None,
                    changelog=None, previous_version=None,
                    previous_revision=None):
        errors = []
        self._release(self.settings.pre_release_commands, errors=errors)
        if errors and self.settings.cancel_on_error:
            raise ReleaseError("The release was cancelled due to the "
                               "following failed pre-release commands:\n%s"
                               % '\n\n'.join(errors))

    def post_release(self, user, install_path, release_message=None,
                     changelog=None, previous_version=None,
                     previous_revision=None):
        self._release(self.settings.post_release_commands)


def register_plugin():
    return CommandReleaseHook
