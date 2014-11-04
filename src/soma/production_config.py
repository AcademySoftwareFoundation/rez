from rez.colorize import alias as alias_color, heading, error
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.util import propertycache, split_path, print_colored_columns
from soma.exceptions import SomaError, SomaNotFoundError, SomaDataError
from soma.file_store import FileStore
from soma.profile import Profile
from soma.util import print_columns, overrides_str, alias_str
from fnmatch import fnmatch
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
                releases after the given time.
        """
        self.searchpath = searchpath
        self.num_levels = len(searchpath)
        self.subpath = subpath
        self.time_ = time_
        self.profiles = {}

        self.stores = []
        for path in searchpath:
            if subpath:
                path = os.path.join(path, subpath)
            store = FileStore(path, include_patterns=["*.yaml"])
            self.stores.append(store)

    @propertycache
    def profile_names(self):
        """Get the current profile names.

        Returns:
            List of str: Profile names, in no particular order.
        """
        return self._profile_levels.keys()

    def copy(self, time_):
        """Create a copy of this config, at a different time.

        Returns:
            `ProductionConfig`.
        """
        return ProductionConfig(searchpath=self.searchpath,
                                subpath=self.subpath,
                                time_=time_)

    def profile(self, name):
        """Get a profile."""
        profile_ = self.profiles.get(name)
        if profile_ is not None:
            return profile_

        filename = "%s.yaml" % name
        overrides = self.raw_profile(name)
        overrides_ = []

        for level, content, _, _, _ in overrides:
            store = self.stores[level]
            try:
                data = yaml.load(content)
            except YAMLError as e:
                filepath = os.path.join(store.path, filename)
                raise SomaDataError("Invalid override file %r:\n%s"
                                    % (filepath, str(e)))

            overrides_.append((level, data))

        profile_ = Profile(name, self, overrides_)
        self.profiles[name] = profile_
        return profile_

    def raw_profile(self, name):
        """Return the raw file contents used to create a profile.

        Note this this is not cached. Generally a raw profile is only viewed
        for debugging purposes.

        Returns:
            A list of tuples with each tuple containing:
            - int: Level of the override;
            - str: Contents of the override file;
            - str: Handle of the commit;
            - int: Epoch time of the commit;
            - str: Author.

            The list is is ascending level order.
        """
        levels = self._profile_levels.get(name)
        if not levels:
            raise SomaNotFoundError("No such profile %r" % name)

        overrides = []
        filename = "%s.yaml" % name

        for i in levels:
            store = self.stores[i]
            content, handle, commit_time, author \
                = store.read(filename, time_=self.time_)
            override = (i, content.strip(), handle, commit_time, author)
            overrides.append(override)

        return overrides

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

    def print_info(self, list_mode=False, tools=False, pattern=None,
                   verbose=False):
        """Print a summary of the ProductionConfig.

        Args:
            list_mode (bool): Enable list mode.
            tools (bool): Show tools rather than profiles.
            pattern (str): Glob-like pattern to filter profiles/tools.
        """
        fn = self._print_tools if tools else self._print_profiles
        fn(list_mode, pattern, verbose)

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

    @propertycache
    def _profile_levels(self):
        d = {}
        for i, store in enumerate(self.stores):
            filenames = store.filenames(time_=self.time_)
            for filename in filenames:
                name = os.path.splitext(filename)[0]
                levels = d.setdefault(name, [])
                levels.append(i)
        return d

    def _print_tools(self, list_mode, pattern, verbose):
        # create list of (alias, [profiles], command, print-color)
        entries = {}

        for name in self._profile_levels.iterkeys():
            profile_ = self.profile(name)
            tools = profile_.tools

            for alias, command in tools.iteritems():
                if pattern and not fnmatch(alias, pattern):
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
                row = [alias_str(alias, command),
                       ", ".join(sorted(profiles)),
                       color]
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
        profiles_ = self._profile_levels
        if pattern:
            profiles_ = dict((k, v) for k, v in profiles_.iteritems()
                             if fnmatch(k, pattern))
            if not profiles_:
                return

        if list_mode:
            rows = []
            all_levels = set()

            for name, levels in profiles_.iteritems():
                all_levels |= set(levels)
                row = [name]
                row.append(self._overrides_str(levels))
                if verbose:
                    profile_ = self.profile(name)
                    requires_str = " ".join(map(str, profile_.requires))
                    row.append(requires_str)
                row.append(None)
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
            entries = sorted(profiles_.iterkeys())
            if verbose:
                entries = [(x + self._overrides_str(profiles_[x])) for x in entries]

            print_columns(entries)

    def _overrides_str(self, levels):
        return overrides_str(self.num_levels, levels)
