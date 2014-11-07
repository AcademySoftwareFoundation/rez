from rez.util import print_colored_columns, propertycache, \
    readable_time_duration, _missing
from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.colorize import warning, heading, critical, alias as alias_color, \
    combine, bright, Printer
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.util import VersionError
from rez.vendor.schema.schema import Schema, SchemaError, Optional, Or, And
from soma.file_store import FileStatus
from soma.exceptions import SomaNotFoundError, SomaDataError
from soma.util import glob_transform, alias_str, get_timestamp_str, \
    print_columns, dump_profile_yaml
import time
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
    profile_schema = Schema({
        Optional("new"): Or([basestring], None),
        Optional("requires"): [basestring],
        Optional("tools"): [Or(basestring,
                               And(Schema({basestring: basestring}),
                                   lambda x: len(x) == 1)
                            )]
    })

    lock_schema = Schema({"locked": Or(None, int)})

    def __init__(self, name, parent, overrides, lock_overrides=None):
        """Do not create directly, """
        self.name = name
        self.parent = parent

        # profile overrides
        self._levels = []
        self._overrides = []
        for level, data in overrides:
            self._levels.append(level)
            try:
                data_ = self.profile_schema.validate(data)
                self._overrides.append((level, data_))
            except SchemaError as e:
                raise SomaDataError("Invalid data in %r: %s"
                                    % (self._filepath(level), str(e)))

        # lock overrides
        self._lock_overrides = []
        for level, data in (lock_overrides or []):
            try:
                data_ = self.lock_schema.validate(data)
                self._lock_overrides.append((level, data_))
            except SchemaError as e:
                raise SomaDataError("Invalid data in %r: %s"
                                    % (self._lock_filepath(level), str(e)))

    @property
    def levels(self):
        """The levels that the profile has overrides in.

        Zero is the first path in the configured searchpath.

        Returns:
            list of str: Override levels.
        """
        return self._levels

    @propertycache
    def lock(self):
        """Get the active lock on the profile, if any.

        Returns:
            None if there is no active lock, or an epoch time representing the
            time this profile is locked to.
        """
        locks_ = self._locks
        if locks_:
            return locks_[-1][0]
        else:
            return None

    @propertycache
    def requires(self):
        """Get the package requirements of the profile.

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
        """Get the tools provided by this profile.

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

    def context(self, include_local=False, verbosity=0):
        """Get the context for the profile.

        Args:
            include_local (bool): If True, include local packages in the resolve.

        Returns:
            `ResolvedContext`.
        """
        pkg_paths = None if include_local else config.nonlocal_packages_path
        context = ResolvedContext(self.requires,
                                  package_paths=pkg_paths,
                                  verbosity=verbosity,
                                  timestamp=self.parent.time_)
        return context

    def lock_overrides(self):
        """Return the lock overrides.

        This is the list of locks present in the profile's overrides. The last
        lock determines the actual lock time.

        Returns:
            List of (time, level) 2-tuples, where `time` is the epoch time of
            the lock.
        """
        return self._locks

    def __eq__(self, other):
        """Profiles are equal if they represent equivalent environments - ie
        their tools and package requests are the same."""
        return (isinstance(other, Profile)
                and self.name == other.name
                and self.requires == other.requires
                and self.tools == other.tools)

    def __ne__(self, other):
        return not self.__eq__(other)

    def overrides(self):
        """Get the overrides that were merged to create this profile.

        Returns:
            A list of tuples with each tuple containing:
            - int: Level of the override;
            - dict: The override configuration data.

            The list is is ascending level order.
        """
        return self._overrides

    def raw_overrides(self, blame=False):
        """Get the overrides that were merged to create this profile.

        Unlike `overrides`, this function returns information about the actual
        files that were committed that define the overrides.

        Args:
            blame (bool): If True, each line of the file contents will be
                prefixed with git blame information.

        Returns:
            A list of tuples with each tuple containing:
            - int: Level of the override;
            - str: Contents of the override file;
            - str: Handle of the commit;
            - int: Epoch time of the commit;
            - str: Author;
            - `FileStatus` object.

            The list is in ascending level order.
        """
        return self.parent.raw_profile(self.name, blame=blame)

    def file_log(self, handle):
        """Get the log entry for a particular file commit.

        Unlike `logs`, the content of the file is returned.

        Args:
            handle (str): File handle.

        Returns:
            A 5-tuple containing:
            - int: Level of the override;
            - str: Contents of the file (or None if the file is deleted);
            - int: Epoch time of the file commit;
            - str: Author name;
            - `FileStatus` object.
        """
        logs_ = self.logs()
        logs_ = [x for x in logs_ if x[1] == handle]
        if not logs_:
            raise SomaNotFoundError("Unknown file handle %r in profile %r"
                                    % (handle, self.name))
        level, _, commit_time, author_name, file_status = logs_[0]

        filename = "%s.yaml" % self.name
        store = self.parent.stores[level]
        content, _, _, _ = store.read_from_handle(filename, handle)

        return level, content, commit_time, author_name, file_status

    def logs(self, limit=None, since=None, until=None):
        """Return a list of log entries of files that may affect this profile.

        This effectively provides a list of all updates that have occurred to
        this profile since it was created.

        Args:
            limit (int): Maximum number of entries to return.
            since (`DateTime` or int): Only return entries at or after this time.
            until (`DateTime` or int): Only return entries at or before this time.

        Returns:
            List of 5-tuples where each contains:
            - int: Level of the override;
            - str: File handle;
            - int: Epoch time of the file commit;
            - str: Author name;
            - `FileStatus` object.

            The list is ordered from most recent commit to last.
        """
        filename = "%s.yaml" % self.name
        all_entries = []

        # note that all levels have to be checked, not just those currently
        # containing overrides, because a deleted override is just as important
        # in the log as a changed one
        for level in range(self.parent.num_levels):
            store = self.parent.stores[level]
            entries = store.file_logs(filename=filename, limit=limit,
                                      since=since, until=until)
            entries = (tuple([level] + list(x) for x in entries))
            all_entries.extend(entries)

        entries = sorted(all_entries, key=lambda x: x[2], reverse=True)
        if limit:
            entries = entries[:limit]
        return entries

    def effective_logs(self, packages=True, tools=True, include_ineffective=False,
                       limit=None, since=None, until=None, callback=None,
                       progress_callback=None):
        """Return effective log entries.

        This is the same as `logs`, except that the entries returned are only
        those that affected the profile. Overrides earlier in the searchpath
        may not affect a profile because of further overrides later in the
        searchpath.

        In order to identify the effective log entries, an entire `Profile`
        needs to be constructed for every commit to see if that commit had an
        effect.

        Note:
            This is an expensive operation.

        Args:
            packages (bool): Show log entries that caused the package requirements
                to change.
            tools (bool): Show log entries that caused the tools to change.
            include_ineffective (bool): If True, entries that did NOT cause a
                change are also included. Note that if (for eg) `packages` is
                True and `tools` is False, entries that only change tools will
                also be listed as ineffective.
            limit (int): Maximum number of entries to return.
            since (`DateTime` or int): Only return entries at or after this time.
            until (`DateTime` or int): Only return entries at or before this time.
            callback (callable): Called each time an effective entry is found,
                and is passed 4 args:
                - list of log entries: The same that is returned from `logs`;
                - int: index into log entries;
                - `Profile`: the effective profile;
                - set(str): Set of profile sections that have changed.
                If this returns Falsey, the search is stopped. Note that if
                `include_ineffective` is True, the callback may be called with
                an empty change set, signifying an ineffective entry.
            progress_callback (callable): Called each time a log entry is tested.
                If this returns Falsey, the search is stopped. Takes the
                following args:
                - i (int): Current index into log entries;
                - num_logs (int): Total number of log entries;

        Returns:
            A 2-tuple containing:
            - list of log entries: The same that is returned from `logs`.
            - list of 3-tuples (the 'effective' list), each containing:
                - int: index into the log entries list;
                - `Profile`: The effective profile;
                - set(str): Set of changed profile sections - valid items are
                  "requires" and "tools". If this is empty then the entry is
                  ineffective, and was included because `include_ineffective`
                  is True.

            Note:
                Some entries may have a None profile. This means that all
                override files were deleted during that time, so the profile did
                not exist then.

            Note:
                Some entries may have a -1 profile (int). This means that the
                profile was broken - probably invalid data or a syntax error in
                a config file(s).

            Note:
                If an empty effective list is returned, this means that not
                enough entries were read to find an effective entry.
        """
        assert packages or tools
        logs_ = self.logs(since=since, until=until)
        effective_logs_ = self._effective_logs(
            logs_, packages, tools, include_ineffective, limit, since, callback,
            progress_callback)
        return logs_, effective_logs_

    # -- printing functions

    def print_logs(self, limit=None, since=None, until=None, handle=None,
                   highlight_handle=False, verbose=False):
        """Print file logs.

        Args:
            limit (int): Maximum number of entries to return.
            since (`DateTime` or int): Only print entries at or after this time.
            until (`DateTime` or int): Only print entries at or before this time.
            handle (str): Only print the entry matching this handle, if found.
            highlight_handle (bool): If True, and `handle` is specified, print
                all entries instead of just that matching `handle`, but
                highlight that entry.
        """
        logs_ = self.logs(limit=limit, since=since, until=until)
        if handle and not highlight_handle:
            logs_ = [x for x in logs_ if x[1] == handle]
        if not logs_:
            return

        highlight_index = None
        if highlight_handle:
            indexes = [i for i, x in enumerate(logs_) if x[1] == handle]
            if indexes:
                highlight_index = indexes[0]

        rows = self._get_log_rows(logs_, verbose=verbose)
        if highlight_index is not None:
            row = rows[highlight_index + 2]  # skip header
            color = row[-1]
            if color is None:
                color = bright
            else:
                color = combine(color, bright)
            row[-1] = color

        print_colored_columns(rows)

    def print_effective_logs(self, packages=True, tools=True, handle=None,
                             highlight_handle=False, include_ineffective=False,
                             limit=None, since=None, until=None, verbose=False):
        """Print effective logs."""
        logs_ = self.logs(since=since, until=until)
        if handle and not highlight_handle:
            logs_ = [x for x in logs_ if x[1] == handle]
        if not logs_:
            return

        highlight_index = None
        if highlight_handle:
            indexes = [i for i, x in enumerate(logs_) if x[1] == handle]
            if indexes:
                highlight_index = indexes[0]

        # calc width formatting
        rows = self._get_log_rows(logs_, verbose=verbose)
        rows = rows[:1] + rows[2:]  # ditch header underline
        maxwidths = []

        for i in range(len(rows[0]) - 1):
            w = max(len(x[i]) for x in rows)
            maxwidths.append(w)

        def _print_row(row, status, lock, color):
            row_ = []
            for i, txt in enumerate(row):
                if i < len(row) - 1:
                    padding = (maxwidths[i] - len(txt)) * ' '
                    row_.append(txt + padding)
                else:
                    row_.append(txt)

            row_[0] = status
            if verbose:
                # add trailing LOCK column
                row_[-1] = lock
                row_.append(color)
            else:
                row_[-1] = color

            print_colored_columns([row_])

        def _callback(_1, index, profile_, changed):
            color=None
            lock = '-'
            if profile_ is None:
                status = "??"
                color = critical
            elif profile_ == -1:
                status = "!!"
                color = critical
            else:
                if changed:
                    s = ''
                    if "requires" in changed:
                        s += 'P'
                    if "tools" in changed:
                        s += 'T'
                    if len(s) < 2:
                        s = ' ' + s
                    status = s
                else:  # an ineffective entry
                    status = " -"
                    color = warning

                if profile_.lock:
                    t_str = get_timestamp_str(profile_.lock, short=True)
                    lock = "%d(%s)" % (profile_.lock, t_str)

            if index == highlight_index:
                if color is None:
                    color = bright
                else:
                    color = combine(color, bright)

            _print_row(rows[index], status, lock, color)
            return True

        if verbose:
            # adds a trailing LOCK column
            _print_row(rows[0], '  ', "LOCK", heading)  # heading
            underline_row = ['-' * x for x in maxwidths] + [heading]
            lock_width = len("1415300567")  # just a random epoch string
            _print_row(underline_row, '--', '-' * lock_width, heading)
        else:
            _print_row(rows[0], '  ', '', heading)  # heading
            underline_row = ['-' * x for x in maxwidths] + [heading]
            _print_row(underline_row, '--', '', heading)

        rows = rows[1:]
        self._effective_logs(logs_, packages, tools, include_ineffective, limit,
                             since, callback=_callback)

    def print_simple_info(self, buf=sys.stdout):
        """Print a 'simple' style summary, this is useful for diffing."""
        data = {}

        if self.requires:
            requires_strs = map(str, self.requires)
            data["requires"] = requires_strs

        if self.tools:
            tools_strs = []
            for alias, command in self.tools.iteritems():
                tools_strs.append(alias_str(alias, command))
            data["tools"] = tools_strs

        content = dump_profile_yaml(data).strip()
        print_ = Printer(buf)
        print_(content)

    def print_brief_info(self, packages=True, tools=True, lock=True, verbose=False):
        """Print a brief summary of the profile.

        Args:
            packages (bool): Show package requirements.
            tools (bool): Show tools.
            locks (bool): Show locks.
        """
        print_ = Printer()
        spacer = [False]
        print_headers = ((bool(packages and self.requires),
                          bool(tools and self.tools),
                          bool(lock and self.lock)).count(True) > 1)

        def print_header(title):
            if print_headers:
                if spacer[0]:
                    print_()
                print_(title, heading)
                spacer[0] = True

        if lock and self.lock:
            print_header("LOCK")
            if verbose:
                t_str = get_timestamp_str(self.lock)
                print "%d - %s" % (self.lock, t_str)
            else:
                print self.lock

        if packages and self.requires:
            print_header("REQUIRES")
            entries = map(str, self.requires)
            print_columns(entries)

        if tools and self.tools:
            print_header("TOOLS")
            entries = []
            for alias, command in self.tools.iteritems():
                if command == alias:
                    entry = alias
                else:
                    if verbose:
                        entry = alias_str(alias, command)
                    else:
                        entry = alias
                    entry = alias_color(entry)
                entries.append(entry)
            print_columns(entries)

    def print_info(self, packages=True, tools=True, lock=True, removals=False,
                   verbose=False):
        """Print a summary of the profile.

        Args:
            packages (bool): Show package requirements.
            tools (bool): Show tools.
            removals (bool): Show overrides that have caused removal of a
                package requirement or tool.
        """
        all_levels = set()
        package_rows = []
        tool_rows = []
        lock_rows = []

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

        if lock and self._locks:
            def _print_lock_entry(entry):
                lock_time = entry
                t_str = get_timestamp_str(lock_time, short=True)
                return "%d(%s)" % (lock_time, t_str)

            _add_rows(lock_rows, self._locks, _print_lock_entry)

        if packages and self._requires:
            for overrides in self._requires:
                _add_rows(package_rows, overrides)

        if tools and self._tools:
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

        # do the printing
        rows = []
        first_header = [True]

        def add_header(title):
            row = [title]
            if first_header[0]:
                levels_str = self.parent._overrides_str(all_levels)
                row.extend([levels_str, "LEVEL"])
                if verbose:
                    for i in range(self.parent.num_levels):
                        row.append(self.parent._overrides_str(i))
                row.append(heading)
                rows.extend([row, (None, heading)])
                first_header[0] = False
            else:
                row.extend(["", ""])
                if verbose:
                    for i in range(self.parent.num_levels):
                        row.append("")
                row.append(heading)
                rows.extend([False, row, (None, heading)])

        if package_rows:
            add_header("REQUIRES")
            rows.extend(package_rows)

        if tool_rows:
            add_header("TOOLS")
            rows.extend(tool_rows)

        if lock_rows:
            add_header("LOCK")
            rows.extend(lock_rows)

        print_colored_columns(rows)

    def dump(self, buf=sys.stdout, blame=False, verbose=False):
        """Print the contents of each of the override config files.

        Args:
            buf (file-like object): Where to print to.
            blame (bool): If True, each line of each file will be prefixed with
                git blame information.
        """
        overrides = self.raw_overrides(blame=blame)
        now = int(time.time())

        titles = []
        for level, _, handle, commit_time, author, _ in overrides:
            levels_str = self.parent._overrides_str(level)
            readable_time = readable_time_duration(now - commit_time)
            time_str = "(%s, %s ago)" % (author, readable_time)

            if verbose:
                filepath = self._filepath(level)
                title = "%s %s [%s]" % (levels_str, filepath, handle)
            else:
                path = self.parent.searchpath[level]
                title = "%s %s" % (levels_str, path)

            titles.append((title, time_str))

        print_ = Printer(buf)
        do_formatting = print_.isatty()
        if do_formatting:
            maxwidth = max((len(x) + len(y) + 2) for x, y in titles)
            br = '-' * maxwidth

        for i, (_, content, _, _, _, _) in enumerate(overrides):
            title, time_str = titles[i]
            if do_formatting:
                spacer = (maxwidth - len(title) - len(time_str)) * ' '
                print_(title + spacer + time_str, heading)
                print_(br, heading)
            else:
                txt = "%s %s" % (title, time_str)
                print_(txt, heading)
                print_(len(txt) * '-', heading)

            print_(content)
            if i < len(overrides) - 1:
                print_()

    @propertycache
    def _locks(self):
        # a list of (epoch, level) 2-tuples. The last entry is the active lock.
        return [(y, x) for x, y in self._get_lock_overrides()]

    @propertycache
    def _requires(self):
        # a list where each entry is a list of (request, level) 2-tuples. The
        # last entry of each list is the active override.

        # locking can cause an earlier profile to be used
        actual_profile = self._actual_profile
        if actual_profile:
            return actual_profile._requires

        requires_ = {}

        def _add_override(key, value, level):
            entry = requires_.setdefault(key, (len(requires_), []))
            entry[1].append((value, level))

        overrides = self._get_overrides("requires")

        for level, requires_list in overrides:
            for request_str in requires_list:
                if request_str.startswith('^'):  # removal operator
                    key = request_str[1:]
                    _add_override(key, request_str, level)
                    _add_override('!' + key, request_str, level)
                else:
                    try:
                        request = Requirement(request_str)
                    except VersionError as e:
                        raise SomaDataError("Invalid request string %r in %r"
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

        # locking can cause an earlier profile to be used
        actual_profile = self._actual_profile
        if actual_profile:
            return actual_profile._tools

        i = 0
        tools_ = [{}, {}]
        curr_tools = None
        prev_tools = None
        print_warning = Printer(style=warning)

        overrides = self._get_overrides("tools")

        for level, tools_list in overrides:
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

    def _get_log_rows(self, logs_, verbose=False):
        all_levels = set(x[0] for x in logs_)
        levels_str = self.parent._overrides_str(all_levels)

        rows = []
        row = ['', levels_str, "LEVEL"]
        if verbose:
            row.append("HANDLE")
        row.extend(["AUTHOR", "DATE", heading])
        rows.extend([row, [None, heading]])

        for level, handle, commit_time, author, file_status in logs_:
            color = None
            level_str = self.parent._overrides_str(level)
            path = self.parent.searchpath[level]
            time_str = "%d - %s" % (commit_time, get_timestamp_str(commit_time))

            row = [file_status.abbrev, level_str, path]
            if file_status == FileStatus.deleted:
                color = warning
            if verbose:
                row.append(handle)
            row.extend([author, time_str, color])
            rows.append(row)

        return rows

    def _effective_logs(self, logs_, packages=True, tools=True,
                        include_ineffective=False, limit=None, since=None,
                        callback=None, progress_callback=None):
        if not logs_:
            return []

        def _compare(p1, p2):
            changed = set()

            if packages:
                p1_requires = getattr(p1, "requires", None)
                p2_requires = getattr(p2, "requires", None)
                if p1_requires != p2_requires:
                    changed.add("requires")

            if tools:
                p1_tools = getattr(p1, "tools", None)
                p2_tools = getattr(p2, "tools", None)
                if p1_tools != p2_tools:
                    changed.add("tools")

            return changed

        entries = []
        prev_profile = None
        nlogs = len(logs_)

        for i, (level, handle, commit_time, author, file_status) in enumerate(logs_):
            if progress_callback and not progress_callback(i, nlogs):
                return entries

            config_ = self.parent.copy(commit_time)
            try:
                profile_ = config_.profile(self.name)
            except SomaNotFoundError:
                # profile was missing at this time, all config files deleted
                profile_ = None
            except SomaDataError as e:
                # broken profile, probably invalid data in config file
                profile_ = -1

            def _add(i_, p, changed):
                entries.append((i_, p, changed))
                if callback and not callback(logs_, i_, p, changed):
                    return False
                if limit and (len(entries) >= limit):
                    return False
                return True

            if i:
                changed = _compare(profile_, prev_profile)
                if changed or include_ineffective:
                    if not _add(i - 1, prev_profile, changed):  # an effective log entry
                        return entries

            if limit is None and since is None and i == nlogs - 1:
                # compare to empty profile
                empty_profile = Profile(self.name, self.parent, [])
                changed = _compare(empty_profile, profile_)

                if changed or include_ineffective:
                    _add(i, profile_, changed)  # first ever log entry

            prev_profile = profile_

        return entries

    @propertycache
    def _actual_profile(self):
        """Get the 'actual' profile.

        The current profile may be locked to an earlier time. In this case the
        contents of the current profile are ignored, and instead a profile is
        constructed at the locked time - this is the 'actual' profile.

        Returns:
            `Profile` object, or None if the current profile is also the
            actual profile.
        """
        actual_profile = None
        lock_time = self.lock

        if lock_time is not None and lock_time != self.parent.time_:
            config_ = self.parent.copy(lock_time)
            try:
                actual_profile = config_.profile(self.name)
            except SomaNotFoundError as e:
                raise SomaNotFoundError(
                    "Locked profile %r failed to load profile at time %d: %s"
                    % (self.name, lock_time, str(e)))

        return actual_profile

    def _get_overrides(self, namespace):
        overrides = []
        for level, data in reversed(self._overrides):
            value = data.get(namespace)
            if value:
                overrides.append((level, value))

            new_ = (namespace in data.get("new", []))
            if new_:
                break

        return list(reversed(overrides))

    def _get_lock_overrides(self):
        overrides = []
        for level, data in reversed(self._lock_overrides):
            value = data.get("locked", _missing)
            if value is _missing:
                continue
            elif value is None:
                break  # stops inheritence, like 'new' in profile.yamls
            else:
                overrides.append((level, value))

        return list(reversed(overrides))

    def _filepath(self, level):
        path = self.parent.stores[level].path
        return os.path.join(path, "%s.yaml" % self.name)

    def _lock_filepath(self, level):
        path = self.parent.stores[level].path
        return os.path.join(path, ".%s.lock.yaml" % self.name)

    @classmethod
    def _is_removal(cls, value):
        return isinstance(value, basestring) and value.startswith('^')
