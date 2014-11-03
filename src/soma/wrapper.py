

class Wrapper(object):
    def __init__(self, profile, command):
        """
        Args:
            profile: Parent `Profile` object.
            command (list of str): Command to run in the profile.
        """
        self.profile = profile
        self.command = command

    def run(self, *args):
        """Run the command with the given args."""
        from rez.config import config
        from rez.vendor import argparse

        prefix_char = config.suite_alias_prefix_char
        parser = argparse.ArgumentParser(prefix_chars=prefix_char)

        def _add_argument(*nargs, **kwargs):
            nargs_ = []
            for narg in nargs:
                nargs_.append(narg.replace('=', prefix_char))
            parser.add_argument(*nargs_, **kwargs)

        _add_argument(
            "=a", "==about", action="store_true",
            help="print information about the tool")
        _add_argument(
            "=i", "==interactive", action="store_true",
            help="launch an interactive shell within the tool's configured "
            "environment")
        _add_argument(
            "=l", "==local", action="store_true",
            help="include local packages in the resolve (default: False)")
        _add_argument(
            "=v", "==verbose", action="count", default=0,
            help="verbose mode, repeat for more verbosity")

        opts, tool_args = parser.parse_known_args(args)

        if opts.about:
            self.print_about()
            return 0

        context = self.profile.context(include_local=opts.local,
                                       verbosity=opts.verbose)

        if opts.interactive:
            config.override("prompt", "%s>" % self.profile.name)
            command = None
        else:
            command = self.command + tool_args

        returncode, _, _ = context.execute_shell(block=True,
                                                 command=command,
                                                 quiet=bool(command))
        return returncode

    def print_about(self):
        """Print an info message about the tool."""
        import pipes

        cmd_str = ' '.join(map(pipes.quote, self.command))
        print "Profile: %s" % self.profile.name
        print "Command: %s" % cmd_str
