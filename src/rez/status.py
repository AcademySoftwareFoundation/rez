import sys
import os
import os.path
from rez import __version__
from rez.util import propertycache
from rez.resolved_context import ResolvedContext
from rez.colorize import heading, stream_is_tty
from rez.suite import Suite


class Status(object):
    """Access to current status of the environment.

    The current status tells you things such as if you are within a context, or
    if suite(s) are visible on $PATH.
    """
    def __init__(self):
        pass

    @propertycache
    def context_file(self):
        """Get path to the current context file.

        Returns:
            Str, or None if not in a context.
        """
        return os.getenv("REZ_RXT_FILE")

    @propertycache
    def context(self):
        """Get the current context.

        Returns:
            `ResolvedContext` or None if not in a context.
        """
        path = self.context_file
        return ResolvedContext.load(path) if path else None

    @propertycache
    def suites(self):
        """Get currently visible suites.

        Visible suites are those whos bin path appea on $PATH.

        Returns:
            List of `Suite` objects.
        """
        return Suite.load_visible_suites()

    def print_context_info(self, buf=sys.stdout, verbosity=0):
        """Print information about the current context."""
        context = self.context
        if context is None:
            print >> sys.stderr, "not in a resolved environment context."
            return False

        from rez.colorize import Printer
        _pr = Printer(buf)
        _pr("current context", heading)
        _pr("---------------", heading)
        context.print_info(buf=buf, verbosity=verbosity)
        return True

    def print_suite_info(self, buf=sys.stdout, verbosity=0):
        """Print information about the currently visible suite(s)."""
        suites = self.suites
        if not suites:
            print >> sys.stderr, "no visible suites."
            return False

        from rez.colorize import Printer
        _pr = Printer(buf)

        _pr("%d visible suites:" % len(suites), heading)
        for suite in suites:
            _pr()
            title = "suite: %s" % suite.load_path
            _pr(title, heading)
            _pr("-" * len(title), heading)
            suite.print_info(buf=buf, verbosity=verbosity)
        return True

    def print_brief_info(self, buf=sys.stdout):
        """Print a very brief status message."""
        lines = ["Using Rez v%s" % __version__]
        if self.context:
            nreq = len(self.context.package_requests)
            nres = len(self.context.resolved_packages)
            lines.append("1 active context (%d requested packages, %d resolved "
                         " packages)." % (nreq, nres))
        else:
            lines.append("no active context.")
        if self.suites:
            names = (os.path.basename(x.load_path) for x in self.suites)
            lines.append("%d visible suites (%s)."
                         % (len(self.suites), ", ".join(names)))
        else:
            lines.append("no visible suites.")
        print >> buf, "\n".join(lines)
        return bool(self.context or self.suites)

    def print_info(self, buf=sys.stdout, verbosity=0):
        """Print information about current context and/or suite(s)."""
        print >> buf, "Using Rez v%s" % __version__
        if self.suites:
            print >> buf, ''
            self.print_suite_info(buf, verbosity)
        if self.context:
            print >> buf, ''
            self.print_context_info(buf, verbosity)
        if not (self.suites or self.context):
            print >> sys.stderr, "no current context or visible suites."
            return False
        return True

    def print_tools(self, buf=sys.stdout, verbose=False):
        """Print tools available in current context and/or suite(s)."""
        from rez.colorize import Printer, heading
        _pr = Printer(buf)

        if self.context:
            _pr("current context:", heading)
            self.context.print_tools(buf=buf)

        for suite in self.suites:
            title = "suite: %s" % suite.load_path
            _pr(title, heading)
            suite.print_tools(buf=buf, verbose=verbose)
        return bool(self.context or self.suites)


# singleton
status = Status()
