from rez.packages_ import iter_packages
from rez.utils.data_utils import cached_property
from rez.vendor.version.requirement import VersionedObject
from hashlib import sha1
import fnmatch
import re


class PackageFilter(object):
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
        """Determine if the filter excludes the given package.

        Args:
            package (`Package`): Package to filter.

        Returns:
            bool: True if the package is excluded, False otherwise.
        """
        if not self._excludes:
            return False  # quick out

        def _match(rules):
            if rules:
                for rule in rules:
                    if rule.match(package):
                        return True
            return False

        excludes = self._excludes.get(package.name)
        excl = _match(excludes)
        if not excl:
            excludes = self._excludes.get(None)
            excl = _match(excludes)

        if excl:
            includes = self._includes.get(package.name)
            excl = not _match(includes)
            if excl:
                includes = self._includes.get(None)
                excl = not _match(includes)

        return excl

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

    def add_exclusion(self, rule):
        """Add an exclusion rule.

        Args:
            rule (`Rule`): Rule to exclude on.
        """
        self._add_rule(self._excludes, rule)

    def add_inclusion(self, rule):
        """Add an inclusion rule.

        Args:
            rule (`Rule`): Rule to include on.
        """
        self._add_rule(self._includes, rule)

    def copy(self):
        """Return a shallow copy of the filter."""
        other = PackageFilter.__new__(PackageFilter)
        other._excludes = self._excludes.copy()
        other._includes = self._includes.copy()
        return other

    def __and__(self, other):
        """Combine two filters."""
        result = self.copy()
        for rule in other._excludes.itervalues():
            result.add_exclusion(rule)
        for rule in other._includes.itervalues():
            result.add_inclusion(rule)
        return result

    @cached_property
    def sha(self):
        """Get the sha1 hash string of this filter.

        This is needed because package filters have to be incorporated into
        cache keys when storing resolves, but filters don't have a bounded
        length.
        """
        return sha1(str(self)).hexdigest()

    @cached_property
    def cost(self):
        """Get the approximate cost of this filter.

        Cost is the total cost of the exclusion rules in this filter. The cost
        of family-specific filters is divided by 10.

        Returns:
            float: The approximate cost of the filter.
        """
        total = 0.0
        for family, rules in self._excludes.iteritems():
            cost = sum(x.cost() for x in rules)
            if family:
                cost = cost / float(10)
            total += cost
        return total

    def _add_rule(self, rules_dict, rule):
        family = rule.family()
        rules_ = rules_dict.get(family, [])
        rules_dict[family] = sorted(rules_ + [rule], key=lambda x: x.cost())
        cached_property.uncache(self, "sha")
        cached_property.uncache(self, "cost")

    def __str__(self):
        def _fn(x):
            return (x.cost(), str(x))

        return str((sorted(self._excludes.values(), key=_fn),
                   sorted(self._includes.values(), key=_fn)))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


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
    def _extract_family(cls, s):
        m = cls.family_re.match(s)
        if m:
            return m.group()[:-1]
        return None

    def __repr__(self):
        return str(self)

    family_re = re.compile("[^*?]+" + VersionedObject.sep_regex_str)


class FamilyRule(Rule):
    """A rule that matches all packages in a given package family.
    """
    name = "family"

    def __init__(self, family):
        """Create a family rule.

        Args:
            family (str): Package family.
        """
        self._family = family

    def match(self, package):
        return (package.name == self._family)

    def cost(self):
        return 1

    def __str__(self):
        return "all(%s)" % self._family


class GlobRule(Rule):
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

    def match(self, package):
        return bool(self.regex.match(package.qualified_name))

    def cost(self):
        return 10

    def __str__(self):
        return "%s(%s)" % (self.name, self.txt)


class RequirementRule(Rule):
    """A rule that matches a package if that package does not conflict with a
    given requirement.

    For example, the package 'foo-1.2' would match the requirement rule 'foo<10'.
    """
    name = "requirement"

    def __init__(self, requirement):
        self._requirement = requirement
        self._family = requirement.name

    def match(self, package):
        o = VersionedObject.construct(package.name, package.version)
        return not self._requirement.conflicts_with(o)

    def cost(self):
        return 10

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
            return (package.timestamp >= self.timestamp)
        else:
            return (package.timestamp < self.timestamp)

    def cost(self):
        # This is expensive because it causes a package load
        return 1000

    def __str__(self):
        label = "after" if self.reverse else "before"
        parts = []
        if self._family:
            parts.append(self._family)
        parts.append(str(self.timestamp))
        return "%s(%s)" % (label, ':'.join(parts))
