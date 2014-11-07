from rez.colorize import alias as alias_color, heading, error, warning
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.util import propertycache, split_path, print_colored_columns
from soma.exceptions import SomaError, SomaNotFoundError, SomaDataError
from soma.file_store import FileStore
from soma.profile import Profile
from soma.util import print_columns, overrides_str, alias_str, \
    get_timestamp_str, time_as_epoch
import fnmatch
import os.path
import os


class ProductionConfig(object):
    """A production configuration.

    A production configuration is a configured environment where people do work.
    It is the result of combining data from various override configuration files
    found on a searchpath.
    """
    profiles_path_variable = "REZ_SOMA_PROFILES_PATH"
    profiles_subpath_variable = "REZ_SOMA_PROFILES_SUBPATH"
    timestamp_variable = "REZ_SOMA_TIMESTAMP"

    def __init__(self, searchpath, subpath=None, time_=None):
        """Create a production config.

        Args:
            searchpath (list of str): Paths to find profile overrides.
            subpath (str): If provided, override files are stored under this
                subpath within each searchpath.
            time_ (`DateTime` or int): Ignore profile updates and package
                releases after the given time. If specified, this will also
                ignore any locks.
        """
        self.searchpath = searchpath
        self.num_levels = len(searchpath)
        self.subpath = subpath
        self.profiles = {}

        self.time_ = time_
        if time_ is not None:
            self.time_ = time_as_epoch(time_)

        self.stores = []
        for path in searchpath:
            if subpath:
                path = os.path.join(path, subpath)
            store = FileStore(path, include_patterns=("*.yaml",))
            self.stores.append(store)

    @propertycache
    def profile_names(self):
        """Get the current profile names.

        Returns:
            List of str: Profile names, in no particular order.
        """
        return self._profile_names()

    def copy(self, time_):
        """Create a copy of this config, at a different time.

        Returns:
            `ProductionConfig`.
        """
        return ProductionConfig(searchpath=self.searchpath,
                                subpath=self.subpath,
                                time_=time_)

    def profile(self, name, ignore_locks=False):
        """Get a profile.

        Args:
            ignore_locks (bool): If True, locks on the profile, if present,
                will be ignored.

        Returns:
            `Profile` object.
        """
        profile_ = self.profiles.get(name)
        if profile_ is not None:
            return profile_

        def _read_yaml(filepath, content):
            try:
                data = yaml.load(content) or {}
                return data
            except YAMLError as e:
                raise SomaDataError("Invalid override file %r%s:\n%s"
                                    % (filepath, self._at_time_str(), str(e)))

        def _read_overrides(filename, overrides):
            overrides_ = []
            for level, content, _, _, _, _ in overrides:
                filepath = os.path.join(self.stores[level].path, filename)
                data = _read_yaml(filepath, content)
                overrides_.append((level, data))
            return overrides_

        # read profile overrides
        filename = "%s.yaml" % name
        overrides = self.raw_profile(name)
        profile_overrides_ = _read_overrides(filename, overrides)

        # read lock overrides
        filename = ".%s.lock.yaml" % name
        overrides = self._lock_overrides(name)
        lock_overrides_ = _read_overrides(filename, overrides)

        # create profile
        profile_ = Profile(name, self, profile_overrides_, lock_overrides_)
        self.profiles[name] = profile_
        return profile_

    def raw_profile(self, name, blame=False):
        """Return the raw file contents used to create a profile.

        Note this this is not cached. Generally a raw profile is only viewed
        for debugging purposes.

        Args:
            name (str): Profile name.
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
        return self._profile_overrides(name, blame=blame)

    def shell_code(self, shell=None):
        """Return shell code which, when sourced, creates the configured Soma
        environment.

        This basically involves creating shell aliases / functions for the tools
        available in all the profiles.
        """
        from rez.shells import create_shell
        from rez.rex import RexExecutor, OutputStyle
        from shlex import split as shlex_split

        executor = RexExecutor(interpreter=create_shell(shell),
                               output_style=OutputStyle.eval,
                               shebang=False)

        for name in self.profile_names:
            profile = self.profile(name)
            tools = profile.tools
            for tool_name, tool_command in tools.iteritems():
                if isinstance(tool_command, basestring):
                    tool_command = shlex_split(tool_command)
                command = ["soma", "wrap", name, "--"] + tool_command + ["--"]
                executor.alias(tool_name, command)

        return executor.get_output()

    def __str__(self):
        entries =[self.searchpath]
        if self.subpath:
            entries.append(self.subpath)
        elif self.time_:
            entries.append(None)
        if self.time_:
            entries.append(self.time)
        entries_str = ", ".join("%r" % x for x in entries)
        return "%s(%s)" % (self.__class__.__name__, entries_str)

    def __repr__(self):
        return str(self)

    @classmethod
    def get_current_config(cls, time_=None):
        paths_str = os.getenv(cls.profiles_path_variable)
        if not paths_str:
            raise SomaError("$%s not set" % cls.profiles_path_variable)

        subpath = os.getenv(cls.profiles_subpath_variable)
        paths = split_path(paths_str)

        if time_ is None:
            time_ = os.getenv(cls.timestamp_variable)
            if time_:
                try:
                    time_ = int(time_)
                except:
                    raise SomaError("Invalid timestamp in $%s: %s"
                                    % (cls.timestamp_variable, time_))

        return ProductionConfig(searchpath=paths,
                                subpath=subpath,
                                time_=time_)

    # -- printing functions

    def print_profiles(self, list_mode=False, pattern=None, verbose=False):
        """Print a summary of profiles in the ProductionConfig.

        Args:
            list_mode (bool): Enable list mode.
            pattern (str): Glob-like pattern to filter profiles/tools.
        """
        self._print_profiles(list_mode, pattern, verbose)

    def print_tools(self, list_mode=False, pattern=None, verbose=False):
        """Print a summary of tools in the ProductionConfig.

        Args:
            list_mode (bool): Enable list mode.
            pattern (str): Glob-like pattern to filter profiles/tools.
        """
        self._print_tools(list_mode, pattern, verbose)

    def print_locks(self, list_mode=False, verbose=False):
        """Print a summary of locks in the ProductionConfig.

        Args:
            list_mode (bool): Enable list mode.
        """
        self._print_locks(list_mode, verbose)

    def _profile_names(self):
        names = set()
        for i, store in enumerate(self.stores):
            filenames = store.filenames(time_=self.time_)
            for filename in filenames:
                if not filename.endswith(".lock.yaml"):
                    name = os.path.splitext(filename)[0]
                    names.add(name)
        return names

    def _profile_overrides(self, name, blame=False):
        filename = "%s.yaml" % name
        return self._get_overrides(filename, blame)

    def _lock_overrides(self, name):
        filename = ".%s.lock.yaml" % name
        return self._get_overrides(filename)

    def _get_overrides(self, filename, blame=False):
        overrides = []
        for i in range(self.num_levels):
            store = self.stores[i]
            r = store.read(filename, time_=self.time_, blame=blame)
            if r:
                content, handle, commit_time, author, file_status = r
                if content is not None:
                    content = content.strip()
                override = (i, content, handle, commit_time, author, file_status)
                overrides.append(override)

        return overrides

    def _print_locks(self, list_mode, verbose):
        locks = {}
        for name in self.profile_names:
            profile_ = self.profile(name)
            locks[name] = profile_.lock

        if not locks:
            return

        if list_mode:
            if verbose:
                profiles = [k for k, v in locks.iteritems() if v is not None]
                all_levels = set()

                for name in profiles:
                    profile_ = self.profile(name)
                    overrides = profile_.lock_overrides()
                    all_levels.update(x[-1] for x in overrides)

                levels_str = self._overrides_str(all_levels)
                row = ["PROFILE", "LOCK", levels_str, "LEVEL"]
                for i in range(self.num_levels):
                    row.append(self._overrides_str(i))
                row.append(heading)

                rows = [row, (None, heading)]
                for name in sorted(profiles):
                    profile_ = self.profile(name)
                    t_str = get_timestamp_str(profile_.lock)
                    lock_str = "%d - %s" % (profile_.lock, t_str)
                    row = [name, lock_str]

                    overrides = profile_.lock_overrides()
                    levels = set(x[-1] for x in overrides)
                    levels_str = self._overrides_str(levels)
                    row.append(levels_str)

                    level = overrides[-1][1]
                    row.append(self.searchpath[level])

                    for i in range(self.num_levels):
                        override = [x for x in overrides if x[1] == i]
                        if override:
                            lock_time = override[0][0]
                            t_str = get_timestamp_str(lock_time, short=True)
                            s = "%d(%s)" % (lock_time, t_str)
                        else:
                            s = ''
                        row.append(s)

                    row.append(None)
                    rows.append(row)
            else:
                entries = sorted(locks.iteritems())
                rows = [["PROFILE", "LOCK", heading], (None, heading)]
                for name, lock_time in entries:
                    if lock_time is None:
                        lock_str = '-'
                    else:
                        t_str = get_timestamp_str(lock_time)
                        lock_str = "%d - %s" % (lock_time, t_str)
                    rows.append((name, lock_str, None))

            print_colored_columns(rows)
        else:
            entries = []
            for name, lock_time in sorted(locks.iteritems()):
                if lock_time is not None:
                    if verbose:
                        t_str = get_timestamp_str(lock_time, short=True)
                        entries.append("%s(%s)" % (name, t_str))
                    else:
                        entries.append(name)
            print_columns(entries)

    def _print_tools(self, list_mode, pattern, verbose):
        # create list of (alias, [profiles], command, print-color)
        entries = {}

        for name in self.profile_names:
            profile_ = self.profile(name)
            tools = profile_.tools

            for alias, command in tools.iteritems():
                if pattern and not fnmatch.fnmatch(alias, pattern):
                    continue
                entry = entries.setdefault(alias, [alias, [], command, str])
                entry[1].append(name)

        entries = sorted(entries.itervalues(), key=lambda x: x[0])
        for entry in entries:
            alias, profiles, command = entry[:3]
            if len(profiles) > 1:
                entry[3] = error  # colorise tool conflict
            elif alias != command:
                entry[3] = alias_color  # colorise alias

        if not entries:
            return

        # print
        if list_mode:
            rows = [["TOOL", "PROFILE", heading], (None, heading)]
            for alias, profiles, command, color in entries:
                if verbose:
                    entry = alias_str(alias, command)
                else:
                    entry = alias
                profiles_str = ", ".join(sorted(profiles))
                row = [entry, profiles_str, color]
                rows.append(row)
            print_colored_columns(rows)
        else:
            entries_ = []
            for alias, profiles, _, color in entries:
                s = color(alias)
                if verbose:
                    s += "[%s]" % ", ".join(sorted(profiles))
                entries_.append(s)
            print_columns(entries_)

    def _print_profiles(self, list_mode, pattern, verbose):
        names = sorted(self.profile_names)
        if pattern:
            names = (x for x in names if fnmatch.fnmatch(x, pattern))

        if list_mode:
            rows = []
            all_levels = set()

            for name in names:
                color = None
                profile_ = self.profile(name)
                all_levels.update(profile_.levels)

                if profile_.lock:
                    color = warning
                    if verbose:
                        name += "[LOCKED]"

                row = [name]
                row.append(self._overrides_str(profile_.levels))

                if verbose:
                    requires_str = " ".join(map(str, profile_.requires))
                    row.append(requires_str)

                row.append(color)
                rows.append(row)

            rows = sorted(rows, key=lambda x: x[0])

            levels_str = self._overrides_str(all_levels)
            row = ["PROFILE", levels_str]
            if verbose:
                row.append("REQUIRES")
            row.append(heading)
            rows = [row, (None, heading)] + rows

            print_colored_columns(rows)
        else:
            entries = []
            for name in names:
                profile_ = self.profile(name)
                entry = name
                if profile_.lock:
                    if verbose:
                        entry += "[LOCKED]"
                    entry = warning(entry)
                if verbose:
                    levels_str = self._overrides_str(profile_.levels)
                    entry += levels_str
                entries.append(entry)

            print_columns(entries)

    def _overrides_str(self, levels):
        return overrides_str(self.num_levels, levels)

    def _at_time_str(self):
        if self.time_ is None:
            return ''
        else:
            return " at time %d" % self.time_
