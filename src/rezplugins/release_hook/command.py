from rez.release_hook import ReleaseHook
from rez.vendor.schema.schema import Or
from rez.vendor.sh.sh import Command, ErrorReturnCode, sudo, which
import sys, os


class CommandReleaseHook(ReleaseHook):

    schema_dict = {
        "quiet":            bool,
        "on_error":         Or('stop', 'ignore', 'raise'),
        "pre_commands":     [(basestring,[basestring],Or(None, basestring))],
        "post_commands":    [(basestring,[basestring],Or(None, basestring))]}

    @classmethod
    def name(cls):
        return "command"

    def __init__(self, source_path):
        super(CommandReleaseHook, self).__init__(source_path)

    def execute_command(self, cmd_name, cmd_arguments=[], user=None):
        def _execute_cmd_private(cmd_full_path, arguments, on_error='ignore', quiet=False):
            error_class = None if on_error == 'raise' else ErrorReturnCode
            try:
                result = cmd_full_path(arguments)
                if not quiet:
                    print result.stdout.strip()
            except error_class as err:
                if not quiet:
                    print >> sys.stderr, err.stderr.strip()
                if on_error == 'stop':
                    return 'bail'
            return 'proceed'

        if not os.path.isfile(cmd_name):
            cmd_full_path = which(cmd_name)
        else:
            cmd_full_path = cmd_name

        cmd_env = os.environ.copy()
        if user not in (None, 'root'):
            cmd_env['USER'] = user

        run_cmd = Command(cmd_full_path, env=cmd_env)

        settings = self.package.config.plugins.release_hook.command
        if user == 'root':
            with sudo:
                _execute_cmd_private(run_cmd, cmd_arguments, settings.on_error, settings.quiet)
        else:
            _execute_cmd_private(run_cmd, cmd_arguments, settings.on_error, settings.quiet)

    def pre_release(self, user, install_path, release_message=None,
                    changelog=None, previous_version=None,
                    previous_revision=None):
        settings = self.package.config.plugins.release_hook.command
        for (cmd_name, cmd_arguments, user) in settings.pre_commands:
            if self.execute_command(cmd_name, cmd_arguments, user) == 'bail':
                return

    def post_release(self, user, install_path, release_message=None,
                     changelog=None, previous_version=None,
                     previous_revision=None):
        settings = self.package.config.plugins.release_hook.command
        for (cmd_name, cmd_arguments, user) in settings.post_commands:
            if self.execute_command(cmd_name, cmd_arguments, user) == 'bail':
                return


def register_plugin():
    return CommandReleaseHook
