from rez.release_hook import ReleaseHook
import sh
import sys


class CommandReleaseHook(ReleaseHook):

    schema_dict = {
        "pre_commands":     [(basestring,[basestring],bool)],
        "post_commands":    [(basestring,[basestring],bool)]}

    @classmethod
    def name(cls):
        return "command"

    def __init__(self, source_path):
        super(CommandReleaseHook, self).__init__(source_path)

    def execute_command(self, cmd_full_path, cmd_arguments=[], cmd_sudo=False):
        run_cmd = sh.Command(cmd_full_path)
        def _execute_cmd_private(cmd, arguments):
            try:
                result = cmd(arguments)
                print result.stdout.strip()
            except sh.ErrorReturnCode, err:
                print >> sys.stderr, err.stderr.strip()

        if cmd_sudo:
            with sh.sudo:
                _execute_cmd_private(run_cmd, cmd_arguments)
        else:
            _execute_cmd_private(run_cmd, cmd_arguments)

    def pre_release(self):
        settings = self.package.config.plugins.release_hook.command
        for (cmd_full_path, cmd_arguments, cmd_sudo) in settings.pre_commands:
            self.execute_command(cmd_full_path, cmd_arguments, cmd_sudo)

    def post_release(self):
        settings = self.package.config.plugins.release_hook.command
        for (cmd_full_path, cmd_arguments, cmd_sudo) in settings.post_commands:
            self.execute_command(cmd_full_path, cmd_arguments, cmd_sudo)


def register_plugin():
    return CommandReleaseHook
