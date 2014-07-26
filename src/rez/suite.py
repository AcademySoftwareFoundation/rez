from rez.util import propertycache
from rez.exceptions import SuiteError
from rez.resolved_context import ResolvedContext
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from collections import defaultdict
import os.path
import shutil


class Suite(object):
    """A collection of contexts.

    A suite is a collection of contexts. A suite stores its contexts in a
    single directory, and creates wrapper scripts for each tool in each context,
    which it stores into a single bin directory. When a tool is invoked, it
    executes the actual tool in its associated context. When you add a suite's
    bin directory to PATH, you have access to all these tools, which will
    automatically run in correctly configured environments.

    Tool clashes can occur when a tool of the same name is present in two or
    more contexts. When a context is added to a suite, or prefixed/suffixed,
    that context's tools override tools from other contexts.

    There are several ways to avoid tool name clashes:
    - Hide a tool. This removes it from the suite regardless of its priority.
    - Prefix/suffix a context. When you do this, all the tools in the context
      have the prefix/suffix applied.
    - Individually alias a tool using the `alias_tool` method.
    """
    def __init__(self):
        """Create a suite."""
        self.load_path = None
        self.contexts = {}
        self.next_priority = 1

        self.tools = None
        self.tool_conflicts = None

    @property
    def context_names(self):
        return self.contexts.keys()

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
        return context

    def add_context(self, name, context):
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
                                   context=context,
                                   tool_aliases={},
                                   hidden_tools=set(),
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
        data["priority"] = self._next_priority
        self._flush_tools()

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
        data["priority"] = self._next_priority
        self._flush_tools()

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
        if tool_name not in aliases:
            aliases[tool_name] = tool_alias
            self._flush_tools()

    def dealias_tool(self, context_name, tool_name):
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
            - variant (`Variant`): Variant providing the tool.
        """
        self._update_tools()
        return self.tools

    def get_conflicting_aliases(self):
        """Get a list of tool aliases that have one or more conflicts.

        Returns:
            List of strings.
        """
        self._update_tools()
        return self.tool_conflicts.keys()

    def get_alias_conflicts(self, tool_alias):
        """Get a list of conflicts on the given tool.

        Returns: None if the alias has no conflicts, or a list of dicts, where
            each dict contains:
            - tool_name (str): The original, non-aliased name of the tool;
            - context_name (str): Name of the context containing the tool;
            - variant (`Variant`): Variant providing the tool.
        """
        self._update_tools()
        return self.tool_conflicts.get(tool_alias)

    def to_dict(self):
        contexts_ = {}
        for k, data in self.contexts.iteritems():
            data_ = data.copy()
            if "context" in data_:
                del data_["context"]
            contexts_[k] = data_

        return dict(contexts=contexts_)

    @classmethod
    def from_dict(cls, d):
        s = Suite.__new__(Suite)
        s.load_path = None
        s.tools = None
        s.tool_conflicts = None
        s.contexts = d["contexts"]
        s.next_priority = max(x["priority"]
                              for x in s.contexts.itervalues()) + 1
        return s

    def save(self, path):
        if os.path.exists(path):
            shutil.rmtree(path)
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
            filepath = os.path.join(contexts_path, "%s.rxt" % context_name)
            context.save(filepath)

        # create alias wrappers
        #tools = self.get_tools()


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
        s.load_path = path
        return s

    def _context(self, name):
        data = self.contexts.get(name)
        if not data:
            raise SuiteError("No such context: %r" % name)
        return data

    @property
    def _next_priority(self):
        p = self.next_priority
        self.next_priority += 1
        return p

    def _flush_tools(self):
        self.tools = None
        self.tool_conflicts = None

    def _update_tools(self):
        if self.tools is not None:
            return
        self.tools = {}
        self.tool_conflicts = defaultdict(list)

        for data in sorted(self.contexts.values(),
                           key=lambda x: x["priority"], reverse=True):
            context_name = data["name"]
            tool_aliases = data["tool_aliases"]
            hidden_tools = data["hidden_tools"]
            prefix = data.get("prefix", "")
            suffix = data.get("suffix", "")

            context = self.context(context_name)
            context_tools = context.get_tools(request_only=True)
            for variant, tool_names in context_tools.itervalues():
                for tool_name in tool_names:
                    if tool_name in hidden_tools:
                        continue
                    alias = tool_aliases.get(tool_name)
                    if alias is None:
                        alias = "%s%s%s" % (prefix, tool_name, suffix)

                    entry = dict(tool_name=tool_name,
                                 tool_alias=alias,
                                 context_name=context_name,
                                 variant=variant)

                    if alias in self.tools:
                        self.tool_conflicts[alias].append(entry)
                    else:
                        self.tools[alias] = entry
