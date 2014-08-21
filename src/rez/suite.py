from rez.util import propertycache, create_forwarding_script, columnise
from rez.exceptions import SuiteError, ResolvedContextError
from rez.resolved_context import ResolvedContext
from rez.colorize import heading, warning, critical, local, Printer
from rez.colorize import alias as alias_col
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from collections import defaultdict
import os
import os.path
import shutil
import sys


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
        return self.contexts.keys()

    @propertycache
    def tools_path(self):
        """Get the path that should be added to $PATH to expose this suite's
        tools.

        Returns:
            Absolute path as a string, or None if this suite was not loaded
            from disk.
        """
        return os.path.join(self.load_path, "bin") if self.load_path else None

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

    def add_context(self, name, context, description=None):
        """Add a context to the suite.

        Args:
            name (str): Name to store the context under.
            context (ResolvedContext): Context to add.
            description (str): Optional description of the context, for example
                "Maya for effects artists."
        """
        if name in self.contexts:
            raise SuiteError("Context already in suite: %r" % name)
        if not context.success:
            raise SuiteError("Context is not resolved: %r" % name)

        self.contexts[name] = dict(name=name,
                                   context=context.copy(),
                                   tool_aliases={},
                                   hidden_tools=set(),
                                   description=description,
                                   priority=self._next_priority)
        self._flush_tools()

    def remove_context(self, name):
        """Remove a context from the suite.

        Args:
            name (str): Name of the context to remove.
        """
        _ = self._context(name)
        del self.contexts[name]
        self._flush_tools()

    def set_context_description(self, name, description):
        """Set a context's description.

        Args:
            name (str): Name of the context to prefix.
            description (str): Description of context.
        """
        data = self._context(name)
        data["description"] = description

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
        example, a tool called 'foo' would appear as 'foo<prefix>' in the
        suite's bin path.

        Args:
            name (str): Name of the context to prefix.
            prefix (str): Prefix to apply to tools.
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
            tool_name (str): Name of tool to unhide.
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
            tool_name (str): Name of tool to unhide.
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
        return self.tool_conflicts.keys()

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
        for k, data in self.contexts.iteritems():
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
                                  for x in s.contexts.itervalues()) + 1
        else:
            s.next_priority = 1
        return s

    def save(self, path, verbose=False):
        """Save the suite to disk.

        Note that saving over the top of the same suite is allowed - otherwise,
        if `path` already exists, an error is raised. This is intended to avoid
        accidental deletion of directory trees.
        """
        path = os.path.realpath(path)
        if os.path.exists(path):
            if self.load_path and self.load_path == path:
                if verbose:
                    print "saving over previous suite..."
                for context_name in self.context_names:
                    _ = self.context(context_name)  # load before dir deleted
                shutil.rmtree(path)
            else:
                raise SuiteError("Cannot save, path exists: %r" % path)

        contexts_path = os.path.join(path, "contexts")
        os.makedirs(contexts_path)

        # write suite data
        data = self.to_dict()
        filepath = os.path.join(path, "suite.yaml")
        with open(filepath, "w") as f:
            f.write(yaml.dump(data))

        # write contexts
        for context_name in self.context_names:
            context = self.context(context_name)
            context._set_parent_suite(path, context_name)
            filepath = self._context_path(context_name, path)
            if verbose:
                print "writing %r..." % filepath
            context.save(filepath)

        # create alias wrappers
        tools_path = os.path.join(path, "bin")
        os.makedirs(tools_path)
        if verbose:
            print "creating alias wrappers in %r..." % tools_path

        tools = self.get_tools()
        for tool_alias, d in tools.iteritems():
            tool_name = d["tool_name"]
            context_name = d["context_name"]
            if verbose:
                print ("creating %r -> %r (%s context)..."
                       % (tool_alias, tool_name, context_name))
            filepath = os.path.join(tools_path, tool_alias)
            create_forwarding_script(filepath,
                                     module="suite",
                                     func_name="_FWD__invoke_suite_tool_alias",
                                     context_name=context_name,
                                     tool_name=tool_name)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            open(path)  # raise IOError
        filepath = os.path.join(path, "suite.yaml")
        if not os.path.isfile(filepath):
            raise SuiteError("Not a suite: %r" % path)

        try:
            with open(filepath) as f:
                data = yaml.load(f.read())
        except YAMLError as e:
            raise SuiteError("Failed loading suite: %s" % str(e))

        s = cls.from_dict(data)
        s.load_path = os.path.realpath(path)
        return s

    @classmethod
    def load_visible_suites(cls, paths=None):
        """Get a list of suites whos bin paths are visible on $PATH.

        Returns:
            List of `Suite` objects.
        """
        suites = []
        if paths is None:
            paths = os.getenv("PATH", "").split(os.pathsep)
        for path in paths:
            if path and os.path.isdir(path):
                path_ = os.path.dirname(path)
                filepath = os.path.join(path_, "suite.yaml")
                if os.path.isfile(filepath):
                    suite = cls.load(path_)
                    suites.append(suite)
        return suites

    def print_info(self, buf=sys.stdout, verbosity=0):
        """Prints a message summarising the contents of the suite."""
        _pr = Printer(buf)

        if not self.contexts:
            _pr("Suite is empty.")
            return

        tools = self.get_tools().values()
        context_names = set()
        variants = set()
        context_tools = defaultdict(set)
        context_variants = defaultdict(set)

        for entry in tools:
            context_name = entry["context_name"]
            variant = str(entry["variant"])
            context_names.add(context_name)
            variants.add(variant)
            context_tools[context_name].add(entry["tool_name"])
            context_variants[context_name].add(variant)

        _pr("Suite contains %d tools from %d contexts and %d packages."
            % (len(tools), len(context_names), len(variants)))

        _pr()
        _pr("contexts:", heading)
        _pr()
        rows = [["NAME", "VISIBLE TOOLS", "PATH", "DESCRIPTION"],
                ["----", "-------------", "----", "-----------"]]

        for data in self._sorted_contexts():
            context_name = data["name"]
            context_path = self._context_path(context_name) or '-'
            description = data.get("description") or ""
            ntools = len(context_tools[context_name])
            nvariants = len(context_variants[context_name])
            short_desc = "%d tools from %d packages" % (ntools, nvariants)
            rows.append((context_name, short_desc, context_path, description))
        _pr("\n".join(columnise(rows)))

        if verbosity:
            _pr()
            _pr("tools:", heading)
            _pr()
            self.print_tools(buf=buf, verbose=(verbosity >= 2))

    def print_tools(self, buf=sys.stdout, verbose=False):
        """Print table of tools available in the suite."""
        _pr = Printer(buf)

        rows = [["TOOL", "ALIASING", "PACKAGE", "CONTEXT", ""],
                ["----", "--------", "-------", "-------", ""]]
        colors = [None, None]
        tools = self.get_tools().values()
        hidden_tools = self.get_hidden_tools()

        def _get_row(entry):
            context_name = entry["context_name"]
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
                    v = iter(variant).next()
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
            row = [tool_alias, tool_name, package, context_name, msg]
            return row, col

        for data in self._sorted_contexts():
            context_name = data["name"]
            entries = [x for x in tools if x["context_name"] == context_name]
            for entry in entries:
                entry["hidden"] = False

            if verbose:
                hidden_entries = [x for x in hidden_tools
                                  if x["context_name"] == context_name]
                for entry in hidden_entries:
                    entry["hidden"] = True
                entries.extend(hidden_entries)

            entries = sorted(entries, key=lambda x: x["tool_alias"])

            for entry in entries:
                if entry["hidden"]:
                    row, _ = _get_row(entry)
                    row[-1] = "(hidden)"
                    rows.append(row)
                    colors.append(warning)
                else:
                    row, col = _get_row(entry)
                    rows.append(row)
                    colors.append(col)

                    if verbose:
                        tool_alias = row[0]
                        conflicts = self.get_alias_conflicts(tool_alias)
                        if conflicts:
                            for conflict in conflicts:
                                row, _ = _get_row(conflict)
                                row[-1] = "(not visible)"
                                rows.append(row)
                                colors.append(warning)

        for col, line in zip(colors, columnise(rows)):
            _pr(line, col)

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
        for _, tool_names in context_tools.itervalues():
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

            for variant, tool_names in context_tools.itervalues():
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


class Alias(object):
    """Main execution point of an 'alias' script in a suite.
    """
    def __init__(self, suite_path, context_name, context, tool_name, cli_args):
        self.suite_path = suite_path
        self.context_name = context_name
        self.context = context
        self.tool_name = tool_name
        self.cli_args = cli_args

    @propertycache
    def suite(self):
        return Suite.load(self.suite_path)

    def run(self):
        """Invoke the wrapped script.

        Returns:
            Return code of the command, or 0 if the command is not run.
        """
        from rez.config import config
        from rez.vendor import argparse
        from rez.status import status

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

        opts, tool_args = parser.parse_known_args(self.cli_args)

        if opts.stdin:
            # generally shells will behave as though the '-s' flag was not present
            # when no stdin is available. So here we replicate this behaviour.
            import select
            if not select.select([sys.stdin], [], [], 0.0)[0]:
                opts.stdin = False

        context = self.context
        _pr = Printer()

        # peek
        if opts.peek:
            config.remove_override("quiet")
            new_context = ResolvedContext(context.requested_packages(),
                                          package_paths=context.package_paths,
                                          verbosity=opts.verbose)
            # reapply quiet mode (see cli.forward)
            if "REZ_QUIET" not in os.environ:
                config.override("quiet", True)

            context.print_resolve_diff(new_context)
            return 0

        # patching
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

        def _print_conflicting(variants):
            vars_str = " ".join(x.qualified_package_name for x in variants)
            msg = "Packages (in conflict): %s" % vars_str
            _pr(msg, critical)

        # print info
        if opts.about:
            print "Tool:     %s" % self.tool_name
            print "Suite:    %s" % self.suite_path

            msg = "%s (%r)" % (self.context.load_path, self.context_name)
            if context.load_path is None:
                msg += " (PATCHED)"
            print "Context:  %s" % msg

            variants = context.get_tool_variants(self.tool_name)
            if variants:
                if len(variants) > 1:
                    _print_conflicting(variants)
                else:
                    variant = iter(variants).next()
                    print "Package:  %s" % variant.qualified_package_name

            if opts.verbose:
                print
                context.print_info(verbosity=opts.verbose - 1)
            return 0
        elif opts.versions:
            variants = context.get_tool_variants(self.tool_name)
            if variants:
                if len(variants) > 1:
                    _print_conflicting(variants)
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

                    for col, line in zip(colors, columnise(rows)):
                        _pr(line, col)
            return 0

        # construct command
        cmd = None
        if opts.command:
            cmd = opts.command
        elif opts.interactive:
            config.override("prompt", "%s>" % self.context_name)
            cmd = None
        else:
            cmd = [self.tool_name] + tool_args

        retcode, _, _ = context.execute_shell(command=cmd,
                                              stdin=opts.stdin,
                                              quiet=opts.quiet,
                                              block=True)
        return retcode


def _FWD__invoke_suite_tool_alias(context_name, tool_name, _script, _cli_args):
    suite_path = os.path.dirname(os.path.dirname(_script))
    path = os.path.join(suite_path, "contexts", "%s.rxt" % context_name)
    context = ResolvedContext.load(path)

    alias = Alias(suite_path, context_name, context, tool_name, _cli_args)
    retcode = alias.run()
    sys.exit(retcode)
