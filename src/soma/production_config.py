from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.util import propertycache, split_path, columnise
from soma.exceptions import SomaError
from soma.file_store import FileStore
from soma.profile import Profile
from soma.util import print_columns, overrides_str
import os.path
import os


class ProductionConfig(object):
    """A production configuration.

    A production configuration is a configured environment where people do work.
    It is the result of combining data from various override configuration files,
    found on a searchpath.
    """
    profiles_path_variable = "REZ_SOMA_PROFILES_PATH"
    profiles_subpath_variable = "REZ_SOMA_PROFILES_SUBPATH"
    timestamp_variable = "REZ_SOMA_TIMESTAMP"

    def __init__(self, searchpath, subpath=None, time_=None):
        self.searchpath = searchpath
        self.num_levels = len(searchpath)
        self.subpath = subpath
        self.time_ = time_

        self.stores = []
        for path in searchpath:
            if subpath:
                path = os.path.join(path, subpath)
            store = FileStore(path, include_patterns=["*.yaml"])
            self.stores.append(store)

    @propertycache
    def profiles(self):
        """Get the current profiles.

        Returns:
            dict: A dict containing items:
            - str: Profile name;
            - list: Ascending list of indices indicating where in the searchpath
              the profile has overrides.
        """
        d = {}
        for i, store in enumerate(self.stores):
            filenames = store.filenames(time=self.time_)
            for filename in filenames:
                name = os.path.splitext(filename)[0]
                levels = d.setdefault(name, [])
                levels.append(i)
        return d

    def profile(self, name):
        """Get a profile."""
        levels = self.profiles.get(name)
        if not levels:
            raise SomaError("No such profile %r" % name)

        overrides = []
        filename = "%s.yaml" % name

        for i in levels:
            store = self.stores[i]
            content = store.read(filename)
            try:
                data = yaml.load(content)
            except YAMLError as e:
                filepath = os.path.join(store.path, filename)
                raise SomaError("Invalid override file %r:\n%s"  (filepath, str(e)))

            overrides.append((i, data))

        return Profile(name, self, overrides)

    def print_info(self, list_mode=False, verbose=False):
        profiles_ = self.profiles

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
                rows.append(row)

            rows = sorted(rows, key=lambda x: x[0])

            levels_str = self._overrides_str(all_levels)
            row = ["PROFILE", levels_str]
            if verbose:
                row.append("REQUIRES")
            rows = [row, None] + rows

            print '\n'.join(columnise(rows))
        else:
            entries = sorted(profiles_.iterkeys())
            if verbose:
                entries = [(x + self._overrides_str(profiles_[x])) for x in entries]

            print_columns(entries)

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
    def get_current_config(cls):
        subpath = os.getenv(cls.profiles_subpath_variable)
        paths_str = os.getenv(cls.profiles_path_variable, '')
        paths = split_path(paths_str)

        timestamp = os.getenv(cls.timestamp_variable)
        if timestamp:
            try:
                timestamp = int(timestamp)
            except:
                raise SomaError("Invalid timestamp in $%s: %s"
                                % (cls.timestamp_variable, timestamp))

        return ProductionConfig(searchpath=paths,
                                subpath=subpath,
                                time_=timestamp)

    def _overrides_str(self, levels, ch='+', latest='+'):
        return overrides_str(self.num_levels, levels, ch, latest)
