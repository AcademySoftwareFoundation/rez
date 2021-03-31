from __future__ import print_function

from rez.utils.execution import create_forwarding_script
from rez.exceptions import SuiteError, ResolvedContextError
from rez.resolved_context import ResolvedContext
from rez.utils.data_utils import cached_property
from rez.utils.formatting import columnise, PackageRequest
from rez.utils.colorize import warning, critical, Printer, alias as alias_col
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.utils.yaml import dump_yaml
from rez.vendor.six import six
from collections import defaultdict
import os
import os.path
import shutil
import sys


basestring = six.string_types[0]


class Suite(object):
    """A collection of contexts.

    A suite is a collection of contexts. A suite stores its contexts in a
    single directory, and creates wrapper scripts for each tool in each context,
    which it stores into a single bin directory. When a tool is invoked, it
    executes the actual tool in its associated context. When you add a suite's
    bin directory to PATH, you have access to all these tools, which will
    automatically run in correctly configured environments.

    Tool clashes can occur when a tool of the same name is present in more than
    one context. When a context is added to a suite, or prefixed/suffixed, that
    context's tools override tools from other contexts.

    There are several ways to avoid tool name clashes:
    - Hide a tool. This removes it from the suite even if it does not clash;
    - Prefix/suffix a context. When you do this, all the tools in the context
      have the prefix/suffix applied;
    - Explicitly alias a tool using the `alias_tool` method. This takes
      precedence over context prefix/suffixing.
    """
    def __init__(self):
        """Create a suite."""
        self.load_path = None
        self.contexts = {}
        self.next_priority = 1

        self.tools = None
        self.tool_conflicts = None
        self.hidden_tools = None

    @property
    def context_names(self):
        """Get the names of the contexts in the suite.

        Reurns:
            List of strings.
        """
        return list(self.contexts.keys())

    @cached_property
    def tools_path(self):
        """Get the path that should be added to $PATH to expose this suite's
        tools.

        Returns:
            Absolute path as a string, or None if this suite was not loaded
            from disk.
        """
        return os.path.join(self.load_path, "bin") if self.load_path else None

    def activation_shell_code(self, shell=None):
        """Get shell code that should be run to activate this suite."""
        from rez.shells import create_shell
        from rez.rex import RexExecutor

        executor = RexExecutor(interpreter=create_shell(shell),
                               parent_variables=["PATH"],
                               shebang=False)
        executor.env.PATH.append(self.tools_path)
        return executor.get_output().strip()

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, " ".join(self.context_names))

    def context(self, name):
        """Get a context.

        Args:
            name (str): Name to store the context under.

        Returns:
            `ResolvedContext` object.
        """
        data = self._context(name)
        context = data.get("context")
        if context:
            return context

        assert self.load_path
        context_path = os.path.join(self.load_path, "contexts", "%s.rxt" % name)
        context = ResolvedContext.load(context_path)
        data["context"] = context
        data["loaded"] = True
        return context

    def add_context(self, name, context, prefix_char=None):
        """Add a context to the suite.

        Args:
            name (str): Name to store the context under.
            context (ResolvedContext): Context to add.
        """
        if name in self.contexts:
            raise SuiteError("Context already in suite: %r" % name)
        if not context.success:
            raise SuiteError("Context is not resolved: %r" % name)

        self.contexts[name] = dict(name=name,
                                   context=context.copy(),
                                   tool_aliases={},
                                   hidden_tools=set(),
                                   priority=self._next_priority,
                                   prefix_char=prefix_char)
        self._flush_tools()

    def find_contexts(self, in_request=None, in_resolve=None):
        """Find contexts in the suite based on search criteria.

        Args:
            in_request (str): Match contexts that contain the given package in
                their request.
            in_resolve (str or `Requirement`): Match contexts that contain the
                given package in their resolve. You can also supply a conflict
                requirement - '!foo' will match any contexts whos resolve does
                not contain any version of package 'foo'.

        Returns:
            List of context names that match the search criteria.
        """
        names = self.context_names
        if in_request:
            def _in_request(name):
                context = self.context(name)
                packages = set(x.name for x in context.requested_packages(True))
                return (in_request in packages)

            names = [x for x in names if _in_request(x)]

        if in_resolve:
            if isinstance(in_resolve, basestring):
                in_resolve = PackageRequest(in_resolve)

            def _in_resolve(name):
                context = self.context(name)
                variant = context.get_resolved_package(in_resolve.name)
                if variant:
                    overlap = (variant.version in in_resolve.range)
                    return (
                        (in_resolve.conflict and not overlap)
                        or (overlap and not in_resolve.conflict)
                    )
                else:
                    return in_resolve.conflict

            names = [x for x in names if _in_resolve(x)]
        return names

    def remove_context(self, name):
        """Remove a context from the suite.

        Args:
            name (str): Name of the context to remove.
        """
        self._context(name)
        del self.contexts[name]
        self._flush_tools()

    def set_context_prefix(self, name, prefix):
        """Set a context's prefix.

        This will be applied to all wrappers for the tools in this context. For
        example, a tool called 'foo' would appear as '<prefix>foo' in the
        suite's bin path.

        Args:
            name (str): Name of the context to prefix.
            prefix (str): Prefix to apply to tools.
        """
        data = self._context(name)
        data["prefix"] = prefix
        self._flush_tools()

    def remove_context_prefix(self, name):
        """Remove a context's prefix.

        Args:
            name (str): Name of the context to de-prefix.
        """
        self.set_context_prefix(name, "")

    def set_context_suffix(self, name, suffix):
        """Set a context's suffix.

        This will be applied to all wrappers for the tools in this context. For
        example, a tool called 'foo' would appear as 'foo<suffix>' in the
        suite's bin path.

        Args:
            name (str): Name of the context to suffix.
            suffix (str): Suffix to apply to tools.
        """
        data = self._context(name)
        data["suffix"] = suffix
        self._flush_tools()

    def remove_context_suffix(self, name):
        """Remove a context's suffix.

        Args:
            name (str): Name of the context to de-suffix.
        """
        self.set_context_suffix(name, "")

    def bump_context(self, name):
        """Causes the context's tools to take priority over all others."""
        data = self._context(name)
        data["priority"] = self._next_priority
        self._flush_tools()

    def hide_tool(self, context_name, tool_name):
        """Hide a tool so that it is not exposed in the suite.

        Args:
            context_name (str): Context containing the tool.
            tool_name (str): Name of tool to hide.
        """
        data = self._context(context_name)
        hidden_tools = data["hidden_tools"]
        if tool_name not in hidden_tools:
            self._validate_tool(context_name, tool_name)
            hidden_tools.add(tool_name)
            self._flush_tools()

    def unhide_tool(self, context_name, tool_name):
        """Unhide a tool so that it may be exposed in a suite.

        Note that unhiding a tool doesn't guarantee it can be seen - a tool of
        the same name from a different context may be overriding it.

        Args:
            context_name (str): Context containing the tool.
            tool_name (str): Name of tool to unhide.
        """
        data = self._context(context_name)
        hidden_tools = data["hidden_tools"]
        if tool_name in hidden_tools:
            hidden_tools.remove(tool_name)
            self._flush_tools()

    def alias_tool(self, context_name, tool_name, tool_alias):
        """Register an alias for a specific tool.

        Note that a tool alias takes precedence over a context prefix/suffix.

        Args:
            context_name (str): Context containing the tool.
            tool_name (str): Name of tool to alias.
            tool_alias (str): Alias to give the tool.
        """
        data = self._context(context_name)
        aliases = data["tool_aliases"]
        if tool_name in aliases:
            raise SuiteError("Tool %r in context %r is already aliased to %r"
                             % (tool_name, context_name, aliases[tool_name]))
        self._validate_tool(context_name, tool_name)
        aliases[tool_name] = tool_alias
        self._flush_tools()

    def unalias_tool(self, context_name, tool_name):
        """Deregister an alias for a specific tool.

        Args:
            context_name (str): Context containing the tool.
            tool_name (str): Name of tool to unalias.
        """
        data = self._context(context_name)
        aliases = data["tool_aliases"]
        if tool_name in aliases:
            del aliases[tool_name]
            self._flush_tools()

    def get_tools(self):
        """Get the tools exposed by this suite.

        Returns:
            A dict, keyed by aliased tool name, with dict entries:
            - tool_name (str): The original, non-aliased name of the tool;
            - tool_alias (str): Aliased tool name (same as key);
            - context_name (str): Name of the context containing the tool;
            - variant (`Variant` or set): Variant providing the tool. If the
              tool is in conflict within the context (more than one package has
              a tool of the same name), this will be a set of Variants.
        """
        self._update_tools()
        return self.tools

    def get_tool_filepath(self, tool_alias):
        """Given a visible tool alias, return the full path to the executable.

        Args:
            tool_alias (str): Tool alias to search for.

        Returns:
            (str): Filepath of executable, or None if the tool is not in the
                suite. May also return None because this suite has not been saved
                to disk, so a filepath hasn't yet been established.
        """
        tools_dict = self.get_tools()
        if tool_alias in tools_dict:
            if self.tools_path is None:
                return None
            else:
                return os.path.join(self.tools_path, tool_alias)
        else:
            return None

    def get_tool_context(self, tool_alias):
        """Given a visible tool alias, return the name of the context it
        belongs to.

        Args:
            tool_alias (str): Tool alias to search for.

        Returns:
            (str): Name of the context that exposes a visible instance of this
            tool alias, or None if the alias is not available.
        """
        tools_dict = self.get_tools()
        data = tools_dict.get(tool_alias)
        if data:
            return data["context_name"]
        return None

    def get_hidden_tools(self):
        """Get the tools hidden in this suite.

        Hidden tools are those that have been explicitly hidden via `hide_tool`.

        Returns:
            A list of dicts, where each dict contains:
            - tool_name (str): The original, non-aliased name of the tool;
            - tool_alias (str): Aliased tool name (same as key);
            - context_name (str): Name of the context containing the tool;
            - variant (`Variant`): Variant providing the tool.
        """
        self._update_tools()
        return self.hidden_tools

    def get_conflicting_aliases(self):
        """Get a list of tool aliases that have one or more conflicts.

        Returns:
            List of strings.
        """
        self._update_tools()
        return list(self.tool_conflicts.keys())

    def get_alias_conflicts(self, tool_alias):
        """Get a list of conflicts on the given tool alias.

        Args:
            tool_alias (str): Alias to check for conflicts.

        Returns: None if the alias has no conflicts, or a list of dicts, where
            each dict contains:
            - tool_name (str): The original, non-aliased name of the tool;
            - tool_alias (str): Aliased tool name (same as key);
            - context_name (str): Name of the context containing the tool;
            - variant (`Variant`): Variant providing the tool.
        """
        self._update_tools()
        return self.tool_conflicts.get(tool_alias)

    def validate(self):
        """Validate the suite."""
        for context_name in self.context_names:
            context = self.context(context_name)
            try:
                context.validate()
            except ResolvedContextError as e:
                raise SuiteError("Error in context %r: %s"
                                 % (context_name, str(e)))

    def to_dict(self):
        contexts_ = {}
        for k, data in self.contexts.items():
            data_ = data.copy()
            if "context" in data_:
                del data_["context"]
            if "loaded" in data_:
                del data_["loaded"]
            contexts_[k] = data_

        return dict(contexts=contexts_)

    @classmethod
    def from_dict(cls, d):
        s = Suite.__new__(Suite)
        s.load_path = None
        s.tools = None
        s.tool_conflicts = None
        s.contexts = d["contexts"]
        if s.contexts:
            s.next_priority = max(x["priority"]
                                  for x in s.contexts.values()) + 1
        else:
            s.next_priority = 1
        return s

    def save(self, path, verbose=False):
        """Save the suite to disk.

        Args:
            path (str): Path to save the suite to. If a suite is already saved
                at `path`, then it will be overwritten. Otherwise, if `path`
                exists, an error is raised.
        """
        path = os.path.realpath(path)
        if os.path.exists(path):
            if self.load_path and self.load_path == path:
                if verbose:
                    print("saving over previous suite...")
                for context_name in self.context_names:
                    self.context(context_name)  # load before dir deleted
                shutil.rmtree(path)
            else:
                raise SuiteError("Cannot save, path exists: %r" % path)

        contexts_path = os.path.join(path, "contexts")
        os.makedirs(contexts_path)

        # write suite data
        data = self.to_dict()
        filepath = os.path.join(path, "suite.yaml")
        with open(filepath, "w") as f:
            f.write(dump_yaml(data))

        # write contexts
        for context_name in self.context_names:
            context = self.context(context_name)
            context._set_parent_suite(path, context_name)
            filepath = self._context_path(context_name, path)
            if verbose:
                print("writing %r..." % filepath)
            context.save(filepath)

        # create alias wrappers
        tools_path = os.path.join(path, "bin")
        os.makedirs(tools_path)
        if verbose:
            print("creating alias wrappers in %r..." % tools_path)

        tools = self.get_tools()
        for tool_alias, d in tools.items():
            tool_name = d["tool_name"]
            context_name = d["context_name"]

            data = self._context(context_name)
            prefix_char = data.get("prefix_char")

            if verbose:
                print("creating %r -> %r (%s context)..."
                      % (tool_alias, tool_name, context_name))
            filepath = os.path.join(tools_path, tool_alias)

            create_forwarding_script(filepath,
                                     module="suite",
                                     func_name="_FWD__invoke_suite_tool_alias",
                                     context_name=context_name,
                                     tool_name=tool_name,
                                     prefix_char=prefix_char)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            open(path)  # raise IOError
        filepath = os.path.join(path, "suite.yaml")
        if not os.path.isfile(filepath):
            raise SuiteError("Not a suite: %r" % path)

        try:
            with open(filepath) as f:
                data = yaml.load(f.read(), Loader=yaml.FullLoader)
        except YAMLError as e:
            raise SuiteError("Failed loading suite: %s" % str(e))

        s = cls.from_dict(data)
        s.load_path = os.path.realpath(path)
        return s

    @classmethod
    def visible_suite_paths(cls, paths=None):
        """Get a list of paths to suites that are visible on $PATH.

        Returns:
            List of str.
        """
        suite_paths = []
        if paths is None:
            paths = os.getenv("PATH", "").split(os.pathsep)
        for path in paths:
            if path and os.path.isdir(path):
                path_ = os.path.dirname(path)
                filepath = os.path.join(path_, "suite.yaml")
                if os.path.isfile(filepath):
                    suite_paths.append(path_)
        return suite_paths

    @classmethod
    def load_visible_suites(cls, paths=None):
        """Get a list of suites whos bin paths are visible on $PATH.

        Returns:
            List of `Suite` objects.
        """
        suite_paths = cls.visible_suite_paths(paths)
        suites = [cls.load(x) for x in suite_paths]
        return suites

    def print_info(self, buf=sys.stdout, verbose=False):
        """Prints a message summarising the contents of the suite."""
        _pr = Printer(buf)

        if not self.contexts:
            _pr("Suite is empty.")
            return

        context_names = sorted(self.contexts.keys())
        _pr("Suite contains %d contexts:" % len(context_names))

        if not verbose:
            _pr(' '.join(context_names))
            return

        tools = self.get_tools().values()
        context_tools = defaultdict(set)
        context_variants = defaultdict(set)
        for entry in tools:
            context_name = entry["context_name"]
            context_tools[context_name].add(entry["tool_name"])
            context_variants[context_name].add(str(entry["variant"]))

        _pr()
        rows = [["NAME", "VISIBLE TOOLS", "PATH"],
                ["----", "-------------", "----"]]

        for context_name in context_names:
            context_path = self._context_path(context_name) or '-'
            ntools = len(context_tools.get(context_name, []))
            if ntools:
                nvariants = len(context_variants[context_name])
                short_desc = "%d tools from %d packages" % (ntools, nvariants)
            else:
                short_desc = "no tools"
            rows.append((context_name, short_desc, context_path))

        _pr("\n".join(columnise(rows)))

    def print_tools(self, buf=sys.stdout, verbose=False, context_name=None):
        """Print table of tools available in the suite.

        Args:
            context_name (str): If provided, only print the tools from this
                context.
        """
        def _get_row(entry):
            context_name_ = entry["context_name"]
            tool_alias = entry["tool_alias"]
            tool_name = entry["tool_name"]
            properties = []
            col = None

            variant = entry["variant"]
            if isinstance(variant, set):
                properties.append("(in conflict)")
                col = critical
                if verbose:
                    package = ", ".join(x.qualified_package_name for x in variant)
                else:
                    v = next(iter(variant))
                    package = "%s (+%d more)" % (v.qualified_package_name,
                                                 len(variant) - 1)
            else:
                package = variant.qualified_package_name

            if tool_name == tool_alias:
                tool_name = "-"
            else:
                properties.append("(aliased)")
                if col is None:
                    col = alias_col

            msg = " ".join(properties)
            row = [tool_alias, tool_name, package, context_name_, msg]
            return row, col

        if context_name:
            self._context(context_name)  # check context exists
            context_names = [context_name]
        else:
            context_names = sorted(self.contexts.keys())

        rows = [["TOOL", "ALIASING", "PACKAGE", "CONTEXT", ""],
                ["----", "--------", "-------", "-------", ""]]
        colors = [None, None]

        entries_dict = defaultdict(list)
        for d in self.get_tools().values():
            entries_dict[d["context_name"]].append(d)

        if verbose:
            # add hidden entries
            for d in self.hidden_tools:
                d_ = d.copy()
                d_["hidden"] = True
                entries_dict[d["context_name"]].append(d_)

            # add conflicting tools
            for docs in self.tool_conflicts.values():
                for d in docs:
                    d_ = d.copy()
                    d_["conflicting"] = True
                    entries_dict[d["context_name"]].append(d_)

        for i, context_name in enumerate(context_names):
            entries = entries_dict.get(context_name, [])
            if entries:
                if i:
                    rows.append(('', '', '', '', ''))
                    colors.append(None)

                entries = sorted(entries, key=lambda x: x["tool_alias"].lower())
                for entry in entries:
                    row, col = _get_row(entry)
                    if "hidden" in entry:
                        row[-1] = "(hidden)"
                        rows.append(row)
                        colors.append(warning)
                    elif "conflicting" in entry:
                        row[-1] = "(not visible)"
                        rows.append(row)
                        colors.append(warning)
                    else:
                        rows.append(row)
                        colors.append(col)

        if rows:
            _pr = Printer(buf)
            for col, line in zip(colors, columnise(rows)):
                _pr(line, col)
        else:
            _pr("No tools available.")

    def _context(self, name):
        data = self.contexts.get(name)
        if not data:
            raise SuiteError("No such context: %r" % name)
        return data

    def _context_path(self, name, suite_path=None):
        suite_path = suite_path or self.load_path
        if not suite_path:
            return None
        filepath = os.path.join(suite_path, "contexts", "%s.rxt" % name)
        return filepath

    def _sorted_contexts(self):
        return sorted(self.contexts.values(), key=lambda x: x["priority"])

    @property
    def _next_priority(self):
        p = self.next_priority
        self.next_priority += 1
        return p

    def _flush_tools(self):
        self.tools = None
        self.tool_conflicts = None
        self.hidden_tools = None

    def _validate_tool(self, context_name, tool_name):
        context = self.context(context_name)
        context_tools = context.get_tools(request_only=True)
        for _, tool_names in context_tools.values():
            if tool_name in tool_names:
                return
        raise SuiteError("No such tool %r in context %r"
                         % (tool_name, context_name))

    def _update_tools(self):
        if self.tools is not None:
            return
        self.tools = {}
        self.hidden_tools = []
        self.tool_conflicts = defaultdict(list)

        for data in reversed(self._sorted_contexts()):
            context_name = data["name"]
            tool_aliases = data["tool_aliases"]
            hidden_tools = data["hidden_tools"]
            prefix = data.get("prefix", "")
            suffix = data.get("suffix", "")

            context = self.context(context_name)
            context_tools = context.get_tools(request_only=True)

            for variant, tool_names in context_tools.values():
                for tool_name in tool_names:
                    alias = tool_aliases.get(tool_name)
                    if alias is None:
                        alias = "%s%s%s" % (prefix, tool_name, suffix)

                    entry = dict(tool_name=tool_name,
                                 tool_alias=alias,
                                 context_name=context_name,
                                 variant=variant)

                    if tool_name in hidden_tools:
                        self.hidden_tools.append(entry)
                        continue

                    existing_entry = self.tools.get(alias)
                    if existing_entry:
                        if existing_entry.get("context_name") == context_name:
                            # the same tool is provided in the same context by
                            # more than one package.
                            existing_variant = existing_entry["variant"]
                            if isinstance(existing_variant, set):
                                existing_variant.add(variant)
                            else:
                                existing_entry["variant"] = set([existing_variant,
                                                                 variant])
                        else:
                            self.tool_conflicts[alias].append(entry)
                    else:
                        self.tools[alias] = entry


def _FWD__invoke_suite_tool_alias(context_name, tool_name, prefix_char=None,
                                  _script=None, _cli_args=None):
    suite_path = os.path.dirname(os.path.dirname(_script))
    path = os.path.join(suite_path, "contexts", "%s.rxt" % context_name)
    context = ResolvedContext.load(path)

    from rez.wrapper import Wrapper
    w = Wrapper.__new__(Wrapper)
    w._init(suite_path, context_name, context, tool_name, prefix_char)
    retcode = w.run(*(_cli_args or []))
    sys.exit(retcode)


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
