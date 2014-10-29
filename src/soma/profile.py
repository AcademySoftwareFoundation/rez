from rez.util import columnise, propertycache
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.util import VersionError
from rez.vendor.schema.schema import Schema, SchemaError, Optional, Or, And
from soma.exceptions import SomaError
from soma.util import glob_transform
import fnmatch
import os.path


class Profile(object):
    """A Soma profile.

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
            overrides (list): List of (level, data) tuples.
        """
        self.name = name
        self.parent = parent
        self._requires = None
        self._tools = None

        # validate data
        self.overrides = [(level, self.schema.validate(data))
                          for (level, data) in overrides]

        self._merge_requires()
        self._merge_tools()

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

        """
        def _command(v):
            v_ = v[-1][0]
            return v_ if isinstance(v, basestring) else v_[-1]

        return dict((k, _command(v)) for k, v in self._tools.iteritems())
        """

    def print_info(self, packages=True, tools=True, removals=False, verbose=False):
        all_levels = set()
        package_rows = []
        tool_rows = []

        # package requires
        if packages:
            for overrides in self._requires:
                request, level = overrides[-1]
                if self._is_removal(request):
                    if removals:
                        package_name = request[1:]
                        request_str = "(removed: %s)" % package_name
                    else:
                        continue
                else:
                    request_str = str(request)

                row = [request_str]
                levels = [x[-1] for x in overrides]
                all_levels |= set(levels)
                row.append(self.parent._overrides_str(levels, 'x', '+'))
                row.append(self.parent.searchpath[level])

                if verbose:
                    for i in range(self.parent.num_levels):
                        override = [x for x in overrides if x[1] == i]
                        if override:
                            request, level = override[0]
                            s = str(request)
                        else:
                            s = ''
                        row.append(s)

                package_rows.append(row)

        # tools
        if tools:
            pass

        # header
        row = []
        levels_str = self.parent._overrides_str(all_levels)
        row.append("REQUIRES" if packages else "TOOLS")
        row.append(levels_str)
        row.append("LEVEL")
        if verbose:
            for i in range(self.parent.num_levels):
                row.append(self.parent._overrides_str(i))
        rows = [row, None]
        rows.extend(package_rows)

        if packages and tool_rows:
            row = ["TOOLS", "", ""]
            if verbose:
                for i in range(self.parent.num_levels):
                    row.append("")
            rows.extend([row, None])
            rows.extend(tool_rows)

        print '\n'.join(columnise(rows))

    def _merge_requires(self):
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
        self._requires = [x[-1] for x in items]

    def _merge_tools(self):
        # keys are tool aliases, and each value is a list of ((alias, command), level)
        # 2-tuples. The last entry is the active override.
        i = 0
        tools_ = [{}, {}]
        curr_tools = None
        prev_tools = None

        def _add_override(key, value, level, new_key=None):
            entry = prev_tools.get(key, [])[:]
            entry.append((value, level))
            curr_tools[new_key or key] = entry

        for level, data in self.overrides:
            tools_list = data.get("tools", [])
            curr_tools = tools_[i]
            prev_tools = tools_[1 - i]
            i = 1 - i

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
                        raise SomaError(
                            "Invalid tool entry %r in %r: Using aliasing "
                            "syntax with removal syntax"
                            % (tool_entry, self._filepath(level)))
                    alias = alias[1:]
                elif rename_op:
                    if not aliased:
                        raise SomaError(
                            "Invalid tool entry %r in %r: Using renaming "
                            "syntax with no target name"
                            % (tool_entry, self._filepath(level)))
                    alias = alias[1:]

                if '*' in alias:
                    aliases = fnmatch.filter(prev_tools.iterkeys(), alias)
                    if remove_op:
                        # a remove op in the form '^*', '^*_fx' etc
                        for alias_ in aliases:
                            _add_override(alias_, '^' + alias, level)
                    elif aliased:
                        # a rename op in the form '*': '*_fx'
                        rename_op = True
                        new_alias = command
                        if '*' not in new_alias:
                            raise SomaError(
                                "Invalid tool entry %r in %r: Wildcarded alias "
                                "rename must have wildcarded target name, for "
                                "example ('*': '*_fx')"
                                % (tool_entry, self._filepath(level)))

                        for alias_ in aliases:
                            entry = prev_tools[alias_]
                            prev_value = entry[-1][0]
                            if self._is_removal(prev_value):
                                # renaming a deleted entry - silent fail
                                continue
                            else:
                                assert isinstance(prev_value, tuple)
                                new_alias_ = glob_transform(alias, new_alias, alias_)
                                prev_command = prev_value[-1]
                                value = (new_alias_, prev_command)
                                _add_override(alias_, value, level, new_alias_)
                    else:
                        raise SomaError(
                            "Invalid tool entry %r in %r: Wildcarded alias "
                            "must either be a rename or remove operation - "
                            "valid examples include ('*': '*_fx'), '^foo*'"
                            % (tool_entry, self._filepath(level)))
                elif rename_op:
                    # a rename op in the form '@old_name': 'new_name'
                    new_alias = command
                    entry = prev_tools.get(alias)
                    if not entry:
                        continue
                    prev_value = entry[-1][0]
                    if self._is_removal(prev_value):
                        # renaming a deleted entry - silent fail
                        continue
                    else:
                        assert isinstance(prev_value, tuple)
                        prev_command = prev_value[-1]
                        value = (new_alias, prev_command)
                        _add_override(alias, value, level, new_alias)
                else:
                    # a normal tool entry in the form 'name': 'command'
                    value = (alias, command)
                    _add_override(alias, value, level)

        _tools = tools_[i - 1]
        self._tools = {}
        for alias, entries in _tools.iteritems():
            # skip tools that are only a stack of removal operations
            if any(isinstance(x[0], tuple) for x in entries):
                self._tools[alias] = entries

    def _filepath(self, level):
        path = self.parent.store[level].path
        return os.path.join(path, "%s.yaml" % self.name)

    @classmethod
    def _is_removal(cls, value):
        return isinstance(value, basestring) and value.startswith('^')
