from rez.util import print_colored_columns, propertycache
from rez.colorize import warning, heading, alias as alias_color, Printer
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.util import VersionError
from rez.vendor.schema.schema import Schema, SchemaError, Optional, Or, And
from soma.exceptions import SomaError
from soma.util import glob_transform, alias_str
import fnmatch
import pipes
import os.path
import sys


class Profile(object):
    """A Soma profile.

    A profile is a sequence of 'overrides' - config data that are merged together
    to produce a final list of package requests and tools. For example, consider
    the following sequence of configs (shown as yaml)

        # config #1
        requires:
        - foo-1
        - eek
        - utils-2.0.0

        tools:
        - fooify
        - fooify_help: 'fooify -h'
        - fooster

        # config #2
        requires:
        - bah-2
        - eek-4.3+
        - ^utils  # a remove operation

        tools:
        - bahster
        - ^fooify

    This will produce the merged configuration::

        # merged config
        requires:
        - foo-1
        - eek-4.3+
        - bah-2

        tools:
        - fooify_help : 'fooify -h'
        - fooster
        - bahster

    Soma creates shell aliases for each of the tools in the configuration. When
    run, these aliases resolve the configured environment, then run the command
    within that environment.

    See Soma documentation for a detailed overview of override features (not all
    are shown in this comment).
    """
    schema = Schema({
        Optional("requires"): [basestring],
        Optional("tools"): [Or(basestring,
                               And(Schema({basestring: basestring}),
                                   lambda x: len(x) == 1)
                            )]
    })

    def __init__(self, name, parent, overrides):
        """
        Args:
            parent (`ProductionConfig`).
            overrides (list): List of (level, dict) tuples.
        """
        self.name = name
        self.parent = parent
        self.overrides = [(level, self.schema.validate(data))
                          for (level, data) in overrides]

    @propertycache
    def requires(self):
        """
        Returns:
            List of `Requirement`: Merged requirements of the profile.
        """
        requires_ = []
        for entries in self._requires:
            entry, level = entries[-1]
            if not self._is_removal(entry):
                requires_.append(entry)
        return requires_

    @propertycache
    def tools(self):
        """
        Returns:
            Dict of (alias, command) tuples. Where no aliasing is used, `alias`
            and `command` are the same string.
        """
        tools_ = {}
        for alias, entries in self._tools.iteritems():
            entry, level = entries[-1]
            if not self._is_removal(entry):
                alias_, command = entry
                assert alias_ == alias
                tools_[alias] = command
        return tools_

    def print_info(self, packages=True, tools=True, removals=False, verbose=False):
        """Print summary of the profile.

        Args:
            packages (bool): Show package requirements.
            tools (bool): Show tools.
            removals (bool): Show overrides that have caused removal of a
                package requirement or tool.
        """
        all_levels = set()
        package_rows = []
        tool_rows = []

        def _add_rows(rows, overrides, entry_printer=None, entry_color=None):
            entry_printer = entry_printer or str
            entry_color = entry_color or (lambda x: None)
            color = None

            entry, level = overrides[-1]
            if self._is_removal(entry):
                if removals:
                    package_name = entry[1:]
                    request_str = "(removed: %s)" % package_name
                    color = warning
                else:
                    return
            else:
                request_str = entry_printer(entry)

            row = [request_str]
            levels = [x[-1] for x in overrides]
            all_levels.update(levels)
            row.append(self.parent._overrides_str(levels))
            row.append(self.parent.searchpath[level])

            if verbose:
                for i in range(self.parent.num_levels):
                    override = [x for x in overrides if x[1] == i]
                    if override:
                        entry = override[0][0]
                        if self._is_removal(entry):
                            s = str(entry)
                        else:
                            s = entry_printer(entry)
                    else:
                        s = ''
                    row.append(s)

            if color is None:
                color = entry_color(entry)
            row.append(color)
            rows.append(row)

        # package requires
        if packages:
            for overrides in self._requires:
                _add_rows(package_rows, overrides)

        # tools
        if tools:
            def _print_tool_entry(entry):
                alias, command = entry
                return alias_str(alias, command)

            def _tool_entry_color(entry):
                alias, command = entry
                if alias == command:
                    return None
                else:
                    return alias_color

            items = sorted(self._tools.iteritems(), key=lambda x: x[0])
            tool_overrides = [x[1] for x in items]
            for overrides in tool_overrides:
                _add_rows(tool_rows, overrides, _print_tool_entry, _tool_entry_color)

        # header
        row = []
        levels_str = self.parent._overrides_str(all_levels)
        row.append("REQUIRES" if packages else "TOOLS")
        row.append(levels_str)
        row.append("LEVEL")
        if verbose:
            for i in range(self.parent.num_levels):
                row.append(self.parent._overrides_str(i))
        row.append(heading)
        rows = [row, (None, heading)]
        rows.extend(package_rows)

        if tool_rows:
            if packages:
                row = ["TOOLS", "", ""]
                if verbose:
                    for i in range(self.parent.num_levels):
                        row.append("")
                row.append(heading)
                rows.extend([False, row, (None, heading)])
            rows.extend(tool_rows)

        print_colored_columns(rows)

    @propertycache
    def _requires(self):
        # each entry is a list of (request, level) 2-tuples. The last entry is
        # the active override.
        requires_ = {}

        def _add_override(key, value, level):
            entry = requires_.setdefault(key, (len(requires_), []))
            entry[1].append((value, level))

        for level, data in self.overrides:
            requires_list = data.get("requires", [])
            for request_str in requires_list:
                if request_str.startswith('^'):  # removal operator
                    key = request_str[1:]
                    _add_override(key, request_str, level)
                    _add_override('!' + key, request_str, level)
                else:
                    try:
                        request = Requirement(request_str)
                    except VersionError as e:
                        raise SomaError("Invalid request string %r in %r"
                                        % (request_str, self._filepath(level)))

                    key = request.name
                    if request.conflict:
                        key = '!' + key

                    _add_override(key, request, level)

        # remove removal operations that don't remove anything
        requires_list_ = []
        for index, overrides in requires_.itervalues():
            if any(isinstance(x[0], Requirement) for x in overrides):
                requires_list_.append((index, overrides))

        items = sorted(requires_list_, key=lambda x: x[0])
        result = [x[-1] for x in items]
        return result

    @propertycache
    def _tools(self):
        # keys are tool aliases, and each value is a list of ((alias, command), level)
        # 2-tuples. The last entry is the active override.
        i = 0
        tools_ = [{}, {}]
        curr_tools = None
        prev_tools = None
        print_warning = Printer(style=warning)

        for level, data in self.overrides:
            tools_list = data.get("tools", [])
            touched_aliases = set()
            curr_tools = tools_[i]
            prev_tools = tools_[1 - i]
            curr_tools.clear()
            i = 1 - i

            def _add_override(alias, value, level, new_alias=None):
                entry = prev_tools.get(alias, [])[:]
                entry.append((value, level))
                curr_tools[new_alias or alias] = entry
                touched_aliases.add(alias)
                if new_alias:
                    touched_aliases.add(new_alias)

            def _do_removal(alias, level):
                entry = prev_tools.get(alias)
                touched_aliases.add(alias)
                if entry:
                    del prev_tools[alias]
                    entry.append(('^' + alias, level))
                    curr_tools[alias] = entry

            for tool_entry in tools_list:
                aliased = isinstance(tool_entry, dict)
                if aliased:
                    alias, command = tool_entry.items()[0]
                else:
                    alias = tool_entry
                    command = tool_entry

                remove_op = alias.startswith('^')
                rename_op = alias.startswith('@')

                if remove_op:
                    if aliased:
                        print_warning(
                            "Invalid tool entry %r in %r: uses aliasing "
                            "syntax with removal syntax"
                            % (tool_entry, self._filepath(level)))
                        continue
                    alias = alias[1:]
                elif rename_op:
                    if not aliased:
                        print_warning(
                            "Invalid tool entry %r in %r: uses "
                            "renaming syntax with no target name"
                            % (tool_entry, self._filepath(level)))
                        continue
                    alias = alias[1:]

                if '*' in alias:
                    aliases = fnmatch.filter(prev_tools.iterkeys(), alias)
                    if remove_op:
                        # a remove op in the form '^*', '^*_fx' etc
                        for alias_ in aliases:
                            _do_removal(alias_, level)
                    elif aliased:
                        # a rename op in the form '*': '*_fx'
                        rename_op = True
                        new_alias = command
                        if '*' not in new_alias:
                            print_warning(
                                "Invalid tool entry %r in %r: wildcarded alias "
                                "rename must have wildcarded target name, for "
                                "example ('*': '*_fx')"
                                % (tool_entry, self._filepath(level)))
                            continue

                        for alias_ in aliases:
                            entry = prev_tools[alias_]
                            prev_value = entry[-1][0]
                            if self._is_removal(prev_value):
                                continue  # renaming a deleted tool - silent skip
                            else:
                                assert isinstance(prev_value, tuple)
                                new_alias_ = glob_transform(alias, new_alias, alias_)
                                prev_command = prev_value[-1]
                                value = (new_alias_, prev_command)
                                _add_override(alias_, value, level, new_alias_)
                    else:
                        print_warning(
                            "Invalid tool entry %r in %r: wildcarded alias "
                            "must either be a rename or remove operation - "
                            "valid examples include ('*': '*_fx'), '^foo*'"
                            % (tool_entry, self._filepath(level)))
                        continue
                elif remove_op:
                    # a remove op in the form '^foo'
                    _do_removal(alias, level)
                elif rename_op:
                    # a rename op in the form '@old_name': 'new_name'
                    new_alias = command
                    entry = prev_tools.get(alias)
                    if not entry:
                        continue  # renaming a nonexistent tool - silent skip
                    prev_value = entry[-1][0]
                    if self._is_removal(prev_value):
                        continue  # renaming a deleted entry - silent skip
                    else:
                        prev_command = prev_value[-1]
                        value = (new_alias, prev_command)
                        _add_override(alias, value, level, new_alias)
                else:
                    # a normal tool entry in the form 'name' or 'name': 'command'
                    value = (alias, command)
                    _add_override(alias, value, level)

            # inherit unchanged tools
            prev_keys = set(prev_tools.iterkeys())
            curr_keys = set(curr_tools.iterkeys())
            unchanged_keys = prev_keys - curr_keys - touched_aliases
            for key in unchanged_keys:
                curr_tools[key] = prev_tools[key]

        tools_ = tools_[i - 1]
        result = {}
        for alias, entries in tools_.iteritems():
            # skip tools that are only a stack of removal operations
            if any(isinstance(x[0], tuple) for x in entries):
                result[alias] = entries
        return result

    def _filepath(self, level):
        path = self.parent.stores[level].path
        return os.path.join(path, "%s.yaml" % self.name)

    @classmethod
    def _is_removal(cls, value):
        return isinstance(value, basestring) and value.startswith('^')
