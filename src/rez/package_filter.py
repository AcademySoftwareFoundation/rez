from rez.vendor.six import six
from rez.packages_ import iter_packages
from rez.exceptions import ConfigurationError
from rez.config import config
from rez.utils.data_utils import cached_property, cached_class_property
from rez.vendor.version.requirement import VersionedObject, Requirement
from hashlib import sha1
import fnmatch
import re


class PackageFilterBase(object):
    def excludes(self, package):
        """Determine if the filter excludes the given package.

        Args:
            package (`Package`): Package to filter.

        Returns:
            `Rule` object that excludes the package, or None if the package was
            not excluded.
        """
        raise NotImplementedError

    def add_exclusion(self, rule):
        """Add an exclusion rule.

        Args:
            rule (`Rule`): Rule to exclude on.
        """
        raise NotImplementedError

    def add_inclusion(self, rule):
        """Add an inclusion rule.

        Args:
            rule (`Rule`): Rule to include on.
        """
        raise NotImplementedError

    @classmethod
    def from_pod(cls, data):
        """Convert from POD types to equivalent package filter."""
        raise NotImplementedError

    def to_pod(self):
        """Convert to POD type, suitable for storing in an rxt file."""
        raise NotImplementedError

    def iter_packages(self, name, range_=None, paths=None):
        """Same as iter_packages in packages.py, but also applies this filter.

        Args:
            name (str): Name of the package, eg 'maya'.
            range_ (VersionRange or str): If provided, limits the versions returned
                to those in `range_`.
            paths (list of str, optional): paths to search for packages, defaults
                to `config.packages_path`.

        Returns:
            `Package` iterator.
        """
        for package in iter_packages(name, range_, paths):
            if not self.excludes(package):
                yield package

    @property
    def sha1(self):
        return sha1(str(self).encode("ascii")).hexdigest()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class PackageFilter(PackageFilterBase):
    """A package filter.

    A package filter is a set of rules that hides some packages but leaves others
    visible. For example, a package filter might be used to hide all packages
    whos version ends in the string '.beta'. A package filter might also be used
    simply to act as a blacklist, hiding some specific packages that are known
    to be problematic.

    Rules can be added as 'exclusion' or 'inclusion' rules. A package is only
    excluded iff it matches one or more exclusion rules, and does not match any
    inclusion rules.
    """
    def __init__(self):
        self._excludes = {}
        self._includes = {}

    def excludes(self, package):
        if not self._excludes:
            return None  # quick out

        def _match(rules):
            if rules:
                for rule in rules:
                    if rule.match(package):
                        return rule
            return None

        excludes = self._excludes.get(package.name)
        excl = _match(excludes)
        if not excl:
            excludes = self._excludes.get(None)
            excl = _match(excludes)

        if excl:
            includes = self._includes.get(package.name)
            incl = _match(includes)
            if incl:
                excl = None
            else:
                includes = self._includes.get(None)
                if _match(includes):
                    excl = None

        return excl

    def add_exclusion(self, rule):
        self._add_rule(self._excludes, rule)

    def add_inclusion(self, rule):
        self._add_rule(self._includes, rule)

    def copy(self):
        """Return a shallow copy of the filter.

        Adding rules to the copy will not alter the source.
        """
        other = PackageFilter.__new__(PackageFilter)
        other._excludes = self._excludes.copy()
        other._includes = self._includes.copy()
        return other

    def __and__(self, other):
        """Combine two filters."""
        result = self.copy()
        for rule in other._excludes.values():
            result.add_exclusion(rule)
        for rule in other._includes.values():
            result.add_inclusion(rule)
        return result

    def __nonzero__(self):
        return bool(self._excludes)

    @cached_property
    def cost(self):
        """Get the approximate cost of this filter.

        Cost is the total cost of the exclusion rules in this filter. The cost
        of family-specific filters is divided by 10.

        Returns:
            float: The approximate cost of the filter.
        """
        total = 0.0
        for family, rules in self._excludes.items():
            cost = sum(x.cost() for x in rules)
            if family:
                cost = cost / float(10)
            total += cost
        return total

    @classmethod
    def from_pod(cls, data):
        f = PackageFilter()
        for namespace, func in (("excludes", f.add_exclusion),
                                ("includes", f.add_inclusion)):
            rule_strs = data.get(namespace, [])
            if isinstance(rule_strs, six.string_types):
                rule_strs = [rule_strs]
            for rule_str in rule_strs:
                rule = Rule.parse_rule(rule_str)
                func(rule)
        return f

    def to_pod(self):
        data = {}
        for namespace, dict_ in (("excludes", self._excludes),
                                 ("includes", self._includes)):
            if dict_:
                rules = []
                for rules_ in dict_.values():
                    rules.extend(map(str, rules_))
                data[namespace] = rules
        return data

    def _add_rule(self, rules_dict, rule):
        family = rule.family()
        rules_ = rules_dict.get(family, [])
        rules_dict[family] = sorted(rules_ + [rule], key=lambda x: x.cost())
        cached_property.uncache(self, "cost")

    def __str__(self):
        return str((sorted(self._excludes.items()),
                    sorted(self._includes.items())))


class PackageFilterList(PackageFilterBase):
    """A list of package filters.

    A package is excluded by a filter list iff any filter within the list
    excludes it.
    """
    def __init__(self):
        self.filters = []

    def add_filter(self, package_filter):
        """Add a filter to the list.

        Args:
            package_filter (`PackageFilter`): Filter to add.
        """
        filters = self.filters + [package_filter]
        self.filters = sorted(filters, key=lambda x: x.cost)

    def add_exclusion(self, rule):
        if self.filters:
            f = self.filters[-1]
            f.add_exclusion(rule)
        else:
            f = PackageFilter()
            f.add_exclusion(rule)
            self.add_filter(f)

    def add_inclusion(self, rule):
        """
        Note:
            Adding an inclusion to a filter list applies that inclusion across
            all filters.
        """
        for f in self.filters:
            f.add_inclusion(rule)

    def excludes(self, package):
        for f in self.filters:
            rule = f.excludes(package)
            if rule:
                return rule
        return None

    def copy(self):
        """Return a copy of the filter list.

        Adding rules to the copy will not alter the source.
        """
        other = PackageFilterList.__new__(PackageFilterList)
        other.filters = [x.copy() for x in self.filters]
        return other

    @classmethod
    def from_pod(cls, data):
        flist = PackageFilterList()
        for dict_ in data:
            f = PackageFilter.from_pod(dict_)
            flist.add_filter(f)
        return flist

    def to_pod(self):
        data = []
        for f in self.filters:
            data.append(f.to_pod())
        return data

    def __nonzero__(self):
        return any(self.filters)

    def __str__(self):
        filters = sorted(self.filters, key=lambda x: (x.cost, str(x)))
        return str(tuple(filters))

    @cached_class_property
    def singleton(cls):
        """Filter list as configured by rezconfig.package_filter."""
        return cls.from_pod(config.package_filter)


# filter that does not exclude any packages
no_filter = PackageFilterList()


class Rule(object):
    name = None

    """Relative cost of rule - cheaper rules are checked first."""
    def match(self, package):
        """Apply the rule to the package.

        Args:
            package (`Package`): Package to filter.

        Returns:
            bool: True if the package matches the filter, False otherwise.
        """
        raise NotImplementedError

    def family(self):
        """Returns a package family string if this rule only applies to a given
        package family, otherwise None."""
        return self._family

    def cost(self):
        """Relative cost of filter. Cheaper filters are applied first."""
        raise NotImplementedError

    @classmethod
    def parse_rule(cls, txt):
        """Parse a rule from a string.

        See rezconfig.package_filter for an overview of valid strings.

        Args:
            txt (str): String to parse.

        Returns:
            `Rule` instance.
        """
        types = {"glob": GlobRule,
                 "regex": RegexRule,
                 "range": RangeRule,
                 "before": TimestampRule,
                 "after": TimestampRule}

        # parse form 'x(y)' into x, y
        label, txt = Rule._parse_label(txt)
        if label is None:
            if '*' in txt:
                label = "glob"
            else:
                label = "range"
        elif label not in types:
            raise ConfigurationError(
                "'%s' is not a valid package filter type" % label)

        rule_cls = types[label]
        txt_ = "%s(%s)" % (label, txt)

        try:
            rule = rule_cls._parse(txt_)
        except Exception as e:
            raise ConfigurationError("Error parsing package filter '%s': %s: %s"
                                     % (txt_, e.__class__.__name__, str(e)))
        return rule

    @classmethod
    def _parse(cls, txt):
        """Create a rule from a string.

        Returns:
            `Rule` instance, or None if the string does not represent an instance
            of this rule type.
        """
        raise NotImplementedError

    @classmethod
    def _parse_label(cls, txt):
        m = cls.label_re.match(txt)
        if m:
            label, txt = m.groups()
            return label, txt
        else:
            return None, txt

    @classmethod
    def _extract_family(cls, txt):
        m = cls.family_re.match(txt)
        if m:
            return m.group()[:-1]
        return None

    def __repr__(self):
        return str(self)

    family_re = re.compile("[^*?]+" + VersionedObject.sep_regex_str)
    label_re = re.compile("^([^(]+)\\(([^\\(\\)]+)\\)$")


class RegexRuleBase(Rule):
    def match(self, package):
        return bool(self.regex.match(package.qualified_name))

    def cost(self):
        return 10

    @classmethod
    def _parse(cls, txt):
        _, txt = Rule._parse_label(txt)
        return cls(txt)

    def __str__(self):
        return "%s(%s)" % (self.name, self.txt)


class RegexRule(RegexRuleBase):
    """A rule that matches a package if its qualified name matches a regex string.

    For example, the package 'foo-1.beta' would match the regex rule '.*\\.beta$'.
    """
    name = "regex"

    def __init__(self, s):
        """Create a regex rule.

        Args:
            s (str): Regex pattern. Eg '.*\\.beta$'.
        """
        self.txt = s
        self._family = self._extract_family(s)
        self.regex = re.compile(s)


class GlobRule(RegexRuleBase):
    """A rule that matches a package if its qualified name matches a glob string.

    For example, the package 'foo-1.2' would match the glob rule 'foo-*'.
    """
    name = "glob"

    def __init__(self, s):
        """Create a glob rule.

        Args:
            s (str): Glob pattern. Eg 'foo.*', '*.beta'.
        """
        self.txt = s
        self._family = self._extract_family(s)
        self.regex = re.compile(fnmatch.translate(s))


class RangeRule(Rule):
    """A rule that matches a package if that package does not conflict with a
    given requirement.

    For example, the package 'foo-1.2' would match the requirement rule 'foo<10'.
    """
    name = "range"

    def __init__(self, requirement):
        self._requirement = requirement
        self._family = requirement.name

    def match(self, package):
        o = VersionedObject.construct(package.name, package.version)
        return not self._requirement.conflicts_with(o)

    def cost(self):
        return 10

    @classmethod
    def _parse(cls, txt):
        _, txt = Rule._parse_label(txt)
        return cls(Requirement(txt))

    def __str__(self):
        return "%s(%s)" % (self.name, str(self._requirement))


class TimestampRule(Rule):
    """A rule that matches a package if that package was released before the
    given timestamp.

    Note:
        The 'timestamp' argument used for resolves is ANDed with any package
        filters - providing a filter containing timestamp rules does not override
        the value of 'timestamp'.

    Note:
        Do NOT use a timestamp rule to mimic what the 'timestamp' resolve argument
        does. 'timestamp' is treated differently - the memcache caching system
        is aware of it, so timestamped resolves get cached. Non-timestamped
        resolves also get cached, but their cache entries are invalidated more
        often (when new packages are released).

        There is still a legitimate case to use a global timestamp rule though.
        You might want to ignore all packages released after time X, except for
        some specific packages that you want to let through. To do this you would
        create a package filter containing a timestamp rule with family=None,
        and other family-specific timestamp rules to override that.
    """
    name = "timestamp"

    def __init__(self, timestamp, family=None, reverse=False):
        """Create a timestamp rule.

        Args:
            timestamp (int): Epoch time.
            family (str): Package family to apply the rule to.
            reverse (bool): If True, reverse the logic so that packages released
                *after* the timestamp are matched.
        """
        self.timestamp = timestamp
        self.reverse = reverse
        self._family = family

    def match(self, package):
        if self.reverse:
            return (package.timestamp > self.timestamp)
        else:
            return (package.timestamp <= self.timestamp)

    def cost(self):
        # This is expensive because it causes a package load
        return 1000

    @classmethod
    def after(cls, timestamp, family=None):
        return cls(timestamp, family=family, reverse=True)

    @classmethod
    def before(cls, timestamp, family=None):
        return cls(timestamp, family=family)

    @classmethod
    def _parse(cls, txt):
        label, txt = Rule._parse_label(txt)
        if ':' in txt:
            family, txt = txt.split(':', 1)
        else:
            family = None

        timestamp = int(txt)
        reverse = (label == "after")
        return cls(timestamp, family=family, reverse=reverse)

    def __str__(self):
        label = "after" if self.reverse else "before"
        parts = []
        if self._family:
            parts.append(self._family)
        parts.append(str(self.timestamp))
        return "%s(%s)" % (label, ':'.join(parts))


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
