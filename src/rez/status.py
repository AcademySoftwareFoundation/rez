from __future__ import print_function
import sys
import os
import os.path
from fnmatch import fnmatch
from rez import __version__
from rez.utils.data_utils import cached_property
from rez.resolved_context import ResolvedContext
from rez.packages_ import iter_packages, Package
from rez.suite import Suite
from rez.wrapper import Wrapper
from rez.utils.colorize import local, warning, critical, Printer
from rez.utils.formatting import print_colored_columns, PackageRequest
from rez.backport.shutilwhich import which


class Status(object):
    """Access to current status of the environment.

    The current status tells you things such as if you are within a context, or
    if suite(s) are visible on $PATH.
    """
    def __init__(self):
        pass

    @cached_property
    def context_file(self):
        """Get path to the current context file.

        Returns:
            Str, or None if not in a context.
        """
        return os.getenv("REZ_RXT_FILE")

    @cached_property
    def context(self):
        """Get the current context.

        Returns:
            `ResolvedContext` or None if not in a context.
        """
        path = self.context_file
        return ResolvedContext.load(path) if path else None

    @cached_property
    def suites(self):
        """Get currently visible suites.

        Visible suites are those whos bin path appea on $PATH.

        Returns:
            List of `Suite` objects.
        """
        return Suite.load_visible_suites()

    @cached_property
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

    # TODO: store this info in env-var instead, remove suite info from context.
    @cached_property
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

    def print_info(self, obj=None, buf=sys.stdout):
        """Print a status message about the given object.

        If an object is not provided, status info is shown about the current
        environment - what the active context is if any, and what suites are
        visible.

        Args:
            obj (str): String which may be one of the following:
                - A tool name;
                - A package name, possibly versioned;
                - A context filepath;
                - A suite filepath;
                - The name of a context in a visible suite.
        """
        if not obj:
            self._print_info(buf)
            return True

        b = False
        for fn in (self._print_tool_info,
                   self._print_package_info,
                   self._print_suite_info,
                   self._print_context_info):
            b_ = fn(obj, buf, b)
            b |= b_
            if b_:
                print('', file=buf)

        if not b:
            print("Rez does not know what '%s' is" % obj, file=buf)
        return b

    def print_tools(self, pattern=None, buf=sys.stdout):
        """Print a list of visible tools.

        Args:
            pattern (str): Only list tools that match this glob pattern.
        """
        seen = set()
        rows = []

        context = self.context
        if context:
            data = context.get_tools()
            conflicts = set(context.get_conflicting_tools().keys())
            for _, (variant, tools) in sorted(data.items()):
                pkg_str = variant.qualified_package_name
                for tool in tools:
                    if pattern and not fnmatch(tool, pattern):
                        continue

                    if tool in conflicts:
                        label = "(in conflict)"
                        color = critical
                    else:
                        label = ''
                        color = None

                    rows.append([tool, '-', pkg_str, "active context", label, color])
                    seen.add(tool)

        for suite in self.suites:
            for tool, d in suite.get_tools().items():
                if tool in seen:
                    continue
                if pattern and not fnmatch(tool, pattern):
                    continue

                label = []
                color = None
                path = which(tool)
                if path:
                    path_ = os.path.join(suite.tools_path, tool)
                    if path != path_:
                        label.append("(hidden by unknown tool '%s')" % path)
                        color = warning

                variant = d["variant"]
                if isinstance(variant, set):
                    pkg_str = ", ".join(variant)
                    label.append("(in conflict)")
                    color = critical
                else:
                    pkg_str = variant.qualified_package_name

                orig_tool = d["tool_name"]
                if orig_tool == tool:
                    orig_tool = '-'

                label = ' '.join(label)
                source = ("context '%s' in suite '%s'"
                          % (d["context_name"], suite.load_path))

                rows.append([tool, orig_tool, pkg_str, source, label, color])
                seen.add(tool)

        _pr = Printer(buf)
        if not rows:
            _pr("No matching tools.")
            return False

        headers = [["TOOL", "ALIASING", "PACKAGE", "SOURCE", "", None],
                   ["----", "--------", "-------", "------", "", None]]
        rows = headers + sorted(rows, key=lambda x: x[0].lower())
        print_colored_columns(_pr, rows)
        return True

    def _print_tool_info(self, value, buf=sys.stdout, b=False):
        word = "is also" if b else "is"
        _pr = Printer(buf)

        def _load_wrapper(filepath):
            try:
                return Wrapper(filepath)
            except:
                return

        # find it on disk
        filepath = None
        unpathed = (os.path.basename(value) == value)
        if unpathed:
            filepath = which(value)

        if filepath is None:
            path = os.path.abspath(value)
            if os.path.exists(path):
                filepath = path

        if not filepath or not os.path.isfile(filepath):
            return False

        # is it a suite wrapper?
        tool_name = os.path.basename(filepath)
        w = _load_wrapper(filepath)
        if w:
            _pr("'%s' %s a suite tool:" % (tool_name, word))
            w.print_about()
            return True

        # is it a tool in a current context?
        if self.context:
            variants = self.context.get_tool_variants(tool_name)
            if variants:
                _pr("'%s' %s a tool in the active context:" % (tool_name, word))
                _pr("Tool:     %s" % tool_name)
                if self.context.load_path:
                    _pr("Context:  %s" % self.context.load_path)

                if len(variants) > 1:
                    vars_str = " ".join(x.qualified_package_name for x in variants)
                    msg = "Packages (in conflict): %s" % vars_str
                    _pr(msg, critical)
                else:
                    variant = next(iter(variants))
                    _pr("Package:  %s" % variant.qualified_package_name)
                return True

        # is it actually a suite wrapper, but it's being hidden by another tool
        # on $PATH with the same name?
        if unpathed:
            for suite in self.suites:
                filepath_ = os.path.join(suite.tools_path, tool_name)
                if os.path.isfile(filepath_):
                    w = _load_wrapper(filepath_)
                    if w:
                        _pr("'%s' %s a suite tool, but is hidden by an unknown tool '%s':"
                            % (tool_name, word, filepath), warning)
                        w.print_about()
                    return True

        return False

    def _print_package_info(self, value, buf=sys.stdout, b=False):
        word = "is also" if b else "is"
        _pr = Printer(buf)

        request_str = os.path.basename(value)
        if request_str != value:
            return False

        def _print_package(package):
            if isinstance(package, Package):
                name = package.qualified_name
            else:
                name = package.qualified_package_name  # Variant
            _pr("Package:  %s" % name)
            path_str = "URI:      %s" % package.uri
            if package.is_local:
                path_str += "  (local)"
            _pr(path_str)

        try:
            req = PackageRequest(request_str)
        except:
            return False
        if req.conflict:
            return False
        package_name = req.name
        version_range = req.range

        # check for the package in the active context
        if self.context:
            variant = self.context.get_resolved_package(package_name)
            if variant and variant.version in version_range:
                _pr("'%s' %s a package in the active context:" % (package_name, word))
                _print_package(variant)
                if self.context.load_path:
                    _pr("Context:  %s" % self.context.load_path)
                return True

        # find the package
        it = iter_packages(package_name, version_range)
        packages = sorted(it, key=lambda x: x.version)

        if packages:
            txt = "'%s' %s a package. The latest version" % (package_name, word)
            if not version_range.is_any():
                txt += " in the range '%s'" % str(version_range)
            txt += " is:"
            _pr(txt)
            _print_package(packages[-1])
            return True

        return False

    def _print_suite_info(self, value, buf=sys.stdout, b=False):
        word = "is also" if b else "is"
        _pr = Printer(buf)

        path = os.path.abspath(value)
        if not os.path.isdir(path):
            return False

        try:
            Suite.load(path)
        except:
            return False

        _pr("'%s' %s a suite. Use 'rez-suite' for more information." % (path, word))
        return True

    def _print_context_info(self, value, buf=sys.stdout, b=False):
        word = "is also" if b else "is"
        _pr = Printer(buf)

        path = os.path.abspath(value)
        if not os.path.isfile(path):
            return False

        try:
            ResolvedContext.load(path)
        except:
            return False

        _pr("'%s' %s a context. Use 'rez-context' for more information." % (path, word))
        return True

    def _print_info(self, buf=sys.stdout):
        lines = ["Using Rez v%s" % __version__]
        if self.context:
            if self.context.load_path:
                line = "\nActive Context: %s" % self.context.load_path
            else:
                line = "\nIn Active Context."
            lines.append(line)
        else:
            lines.append("\nNo active context.")

        if self.suites:
            lines.append("\n%d visible suites:" % len(self.suites))
            for suite in self.suites:
                lines.append(suite.load_path)
        else:
            lines.append("\nNo visible suites.")

        if self.parent_suite:
            context_name = self.active_suite_context_name
            lines.append("\nCurrently within context %r in suite at %s"
                         % (context_name, self.parent_suite.load_path))

        print("\n".join(lines), file=buf)


# singleton
status = Status()


# Copyright 2013-2016 Allan Johns.
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
