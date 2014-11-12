from rez.resolved_context import ResolvedContext
from rez.colorize import heading, local, Printer
from rez.util import propertycache, columnise
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.exceptions import RezSystemError
from rez.exceptions import SuiteError
import os.path
import sys


class Wrapper(object):
    """A Wrapper.

    A wrapper is a tool created by a `Suite`. Wrappers reside in the ./bin
    directory of a suite. They are executable yaml files that are run with the
    internal '_rez-forward' tool.

    When a wrapper is executed, it runs the associated tool within the matching
    context in the suite.
    """
    def __init__(self, filepath):
        """Create a wrapper given its executable file."""
        from rez.suite import Suite

        def _err(msg):
            raise RezSystemError("Invalid executable file %s: %s"
                                 % (filepath, msg))

        with open(filepath) as f:
            content = f.read()
        try:
            doc = yaml.load(content)
            doc = doc["kwargs"]
            context_name = doc["context_name"]
            tool_name = doc["tool_name"]
        except YAMLError as e:
            _err(str(e))

        # check that the suite is there - a wrapper may have been moved out of
        # a suite's ./bin path, which renders it useless.
        suite_path = os.path.dirname(os.path.dirname(filepath))
        try:
            _ = Suite.load(suite_path)
        except SuiteError as e:
            _err(str(e))

        path = os.path.join(suite_path, "contexts", "%s.rxt" % context_name)
        context = ResolvedContext.load(path)
        self._init(suite_path, context_name, context, tool_name)

    def _init(self, suite_path, context_name, context, tool_name):
        self.suite_path = suite_path
        self.context_name = context_name
        self.context = context
        self.tool_name = tool_name

    @propertycache
    def suite(self):
        from rez.suite import Suite
        return Suite.load(self.suite_path)

    def run(self, *args):
        """Invoke the wrapped script.

        Returns:
            Return code of the command, or 0 if the command is not run.
        """
        from rez.config import config
        from rez.vendor import argparse

        prefix_char = config.suite_alias_prefix_char
        parser = argparse.ArgumentParser(prog=self.tool_name,
                                         prefix_chars=prefix_char)

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
            "==versions", action="store_true",
            help="list versions of package providing this tool")
        _add_argument(
            "=c", "==command", type=str, nargs='+', metavar=("COMMAND", "ARG"),
            help="read commands from string, rather than executing the tool")
        _add_argument(
            "=s", "==stdin", action="store_true",
            help="read commands from standard input, rather than executing the tool")
        _add_argument(
            "=p", "==patch", type=str, nargs='*', metavar="PKG",
            help="run the tool in a patched environment")
        _add_argument(
            "==strict", action="store_true",
            help="strict patching. Ignored if ++patch is not present")
        _add_argument(
            "==nl", "==no-local", dest="no_local", action="store_true",
            help="don't load local packages when patching")
        _add_argument(
            "==peek", action="store_true",
            help="diff against the tool's context and a re-resolved copy - "
            "this shows how 'stale' the context is")
        _add_argument(
            "=v", "==verbose", action="count", default=0,
            help="verbose mode, repeat for more verbosity")
        _add_argument(
            "=q", "==quiet", action="store_true",
            help="hide welcome message when entering interactive mode")

        opts, tool_args = parser.parse_known_args(args)

        # print info
        if opts.about:
            return self.print_about()
        elif opts.versions:
            return self.print_package_versions()
        elif opts.peek:
            return self.peek()

        # patching
        context = self.context
        if opts.patch is not None:
            new_request = opts.patch
            request = context.get_patched_request(new_request, strict=opts.strict)
            config.remove_override("quiet")
            pkg_paths = (config.nonlocal_packages_path
                         if opts.no_local else None)

            context = ResolvedContext(request,
                                      package_paths=pkg_paths,
                                      verbosity=opts.verbose)

            # reapply quiet mode (see cli.forward)
            if "REZ_QUIET" not in os.environ:
                config.override("quiet", True)

        if opts.stdin:
            # generally shells will behave as though the '-s' flag was not present
            # when no stdin is available. So here we replicate this behaviour.
            import select
            if not select.select([sys.stdin], [], [], 0.0)[0]:
                opts.stdin = False

        # construct command
        cmd = None
        if opts.command:
            cmd = opts.command
        elif opts.interactive:
            label = self.context_name
            if opts.patch:
                label += '*'
            config.override("prompt", "%s>" % label)
            cmd = None
        else:
            cmd = [self.tool_name] + tool_args

        retcode, _, _ = context.execute_shell(command=cmd,
                                              stdin=opts.stdin,
                                              quiet=opts.quiet,
                                              block=True)
        return retcode

    def print_about(self):
        """Print an info message about the tool."""
        filepath = os.path.join(self.suite_path, "bin", self.tool_name)
        print "Tool:     %s" % self.tool_name
        print "Path:     %s" % filepath
        print "Suite:    %s" % self.suite_path

        msg = "%s (%r)" % (self.context.load_path, self.context_name)
        print "Context:  %s" % msg

        variants = self.context.get_tool_variants(self.tool_name)
        if variants:
            if len(variants) > 1:
                self._print_conflicting(variants)
            else:
                variant = iter(variants).next()
                print "Package:  %s" % variant.qualified_package_name
        return 0

    def print_package_versions(self):
        """Print a list of versions of the package this tool comes from, and
        indicate which version this tool is from."""
        variants = self.context.get_tool_variants(self.tool_name)
        if variants:
            if len(variants) > 1:
                self._print_conflicting(variants)
                return 1
            else:
                from rez.packages import iter_packages
                variant = iter(variants).next()
                it = iter_packages(name=variant.name)
                rows = []
                colors = []

                for pkg in sorted(it, key=lambda x: x.version, reverse=True):
                    if pkg.version == variant.version:
                        name = "* %s" % pkg.qualified_name
                        col = heading
                    else:
                        name = "  %s" % pkg.qualified_name
                        col = local if pkg.is_local else None

                    label = "(local)" if pkg.is_local else ""
                    rows.append((name, pkg.path, label))
                    colors.append(col)

                _pr = Printer()
                for col, line in zip(colors, columnise(rows)):
                    _pr(line, col)
        return 0

    def peek(self):
        config.remove_override("quiet")
        new_context = ResolvedContext(self.context.requested_packages(),
                                      package_paths=context.package_paths,
                                      verbosity=opts.verbose)
        # reapply quiet mode (see cli.forward)
        if "REZ_QUIET" not in os.environ:
            config.override("quiet", True)

        self.context.print_resolve_diff(new_context)
        return 0

    @classmethod
    def _print_conflicting(cls, variants):
        vars_str = " ".join(x.qualified_package_name for x in variants)
        msg = "Packages (in conflict): %s" % vars_str
        Printer()(msg, critical)
