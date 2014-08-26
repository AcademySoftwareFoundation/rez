import sys
import os
from rez import __version__
from rez.util import propertycache
from rez.resolved_context import ResolvedContext
from rez.colorize import heading
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

    @propertycache
    def parent_suite(self):
        """Get the current parent suite.

        A parent suite exists when a context within a suite is active. That is,
        during execution of a tool within a suite, or after a user has entered
        an interactive shell in a suite context, for example via the command-
        line syntax 'tool +i', where 'tool' is an alias in a suite.

        Returns:
            `Suite` object, or None if there is no current parent suite.
        """
        if self.context and self.context.parent_suite_path:
            return Suite.load(self.context.parent_suite_path)
        return None

    @propertycache
    def active_suite_context_name(self):
        """Get the name of the currently active context in a parent suite.

        If a parent suite exists, then an active context exists - this is the
        context that a tool in the suite is currently running in.

        Returns:
            (str) Context name, or None if there is no parent suite (and thus
            no active context).
        """
        if self.context:
            return self.context.suite_context_name
        return None

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
            nreq = len(self.context.requested_packages(False))
            nres = len(self.context.resolved_packages)
            lines.append("\n1 active context (%d requested packages, %d resolved "
                         " packages)." % (nreq, nres))
        else:
            lines.append("\nNo active context.")

        if self.suites:
            lines.append("\n%d visible suites:" % len(self.suites))
            for suite in self.suites:
                lines.append(suite.load_path)
        else:
            lines.append("No visible suites.")

        if self.parent_suite:
            context_name = self.active_suite_context_name
            lines.append("\nCurrently within context %r in suite at %s"
                         % (context_name, self.parent_suite.load_path))

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
