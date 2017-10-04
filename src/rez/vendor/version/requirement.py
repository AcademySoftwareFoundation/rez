from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.util import _Common
import re


class VersionedObject(_Common):
    """Definition of a versioned object, eg "foo-1.0".

    "foo" is also a valid object definiton - when there is no version part, we
    are defining an unversioned object.

    Note that '-', '@' or '#' can be used as the seperator between object name
    and version, however this is purely cosmetic - "foo-1" is the same as "foo@1".
    """
    sep_regex_str = r'[-@#]'
    sep_regex = re.compile(sep_regex_str)

    def __init__(self, s):
        self.name_ = None
        self.version_ = None
        self.sep_ = '-'
        if s is None:
            return

        m = self.sep_regex.search(s)
        if m:
            i = m.start()
            self.name_ = s[:i]
            self.sep_ = s[i]
            ver_str = s[i + 1:]
            self.version_ = Version(ver_str)
        else:
            self.name_ = s
            self.version_ = Version()

    @classmethod
    def construct(cls, name, version=None):
        """Create a VersionedObject directly from an object name and version.

        Args:
            name: Object name string.
            version: Version object.
        """
        other = VersionedObject(None)
        other.name_ = name
        other.version_ = Version() if version is None else version
        return other

    @property
    def name(self):
        """Name of the object."""
        return self.name_

    @property
    def version(self):
        """Version of the object."""
        return self.version_

    def __eq__(self, other):
        return (isinstance(other, VersionedObject)
                and (self.name_ == other.name_)
                and (self.version_ == other.version_))

    def __hash__(self):
        return hash((self.name_, self.version_))

    def __str__(self):
        sep_str = ''
        ver_str = ''
        if self.version_:
            sep_str = self.sep_
            ver_str = str(self.version_)
        return self.name_ + sep_str + ver_str


class Requirement(_Common):
    """Requirement for a versioned object.

    Examples of valid requirement strings:

        foo-1.0
        foo@1.0
        foo#1.0
        foo-1+
        foo-1+<4.3
        foo<3
        foo==1.0.1

    Defines a requirement for an object. For example, "foo-5+" means that you
    require any version of "foo", version 5 or greater. An unversioned
    requirement can also be used ("foo"), this means you require any version of
    foo. You can drop the hyphen between object name and version range if the
    version range starts with a non-alphanumeric character - eg "foo<2".

    There are two different prefixes that can be applied to a requirement:

    - "!": The conflict requirement. This means that you require this version
      range of an object NOT to be present. To conflict with all versions of an
      object, use "!foo".

    - "~": This is known as a "weak reference", and means, "I do not require this
      object, but if present, it must be within this range." It is equivalent to
      the *conflict of the inverse* of the given version range.

    There is one subtle case to be aware of. "~foo" is a requirement that has no
    effect - ie, it means "I do not require foo, but if foo is present, it can
    be any version." This statement is still valid, but will produce a
    Requirement object with a None range.
    """
    sep_regex = re.compile(r'[-@#=<>]')

    def __init__(self, s, invalid_bound_error=True):
        self.name_ = None
        self.range_ = None
        self.negate_ = False
        self.conflict_ = False
        self._str = None
        self.sep_ = '-'
        if s is None:
            return

        self.conflict_ = s.startswith('!')
        if self.conflict_:
            s = s[1:]
        elif s.startswith('~'):
            s = s[1:]
            self.negate_ = True
            self.conflict_ = True

        m = self.sep_regex.search(s)
        if m:
            i = m.start()
            self.name_ = s[:i]
            req_str = s[i:]
            if req_str[0] in ('-', '@', '#'):
                self.sep_ = req_str[0]
                req_str = req_str[1:]

            self.range_ = VersionRange(
                req_str, invalid_bound_error=invalid_bound_error)
            if self.negate_:
                self.range_ = ~self.range_
        elif self.negate_:
            self.name_ = s
            # rare case - '~foo' equates to no effect
            self.range_ = None
        else:
            self.name_ = s
            self.range_ = VersionRange()

    @classmethod
    def construct(cls, name, range=None):
        """Create a requirement directly from an object name and VersionRange.

        Args:
            name: Object name string.
            range: VersionRange object. If None, an unversioned requirement is
                created.
        """
        other = Requirement(None)
        other.name_ = name
        other.range_ = VersionRange() if range is None else range
        return other

    @property
    def name(self):
        """Name of the required object."""
        return self.name_

    @property
    def range(self):
        """VersionRange of the requirement."""
        return self.range_

    @property
    def conflict(self):
        """True if the requirement is a conflict requirement, eg "!foo", "~foo-1".
        """
        return self.conflict_

    @property
    def weak(self):
        """True if the requirement is weak, eg "~foo".

        Note that weak requirements are also conflict requirements, but not
        necessarily the other way around.
        """
        return self.negate_

    def safe_str(self):
        """Return a string representation that is safe for the current filesystem,
        and guarantees that no two different Requirement objects will encode to
        the same value."""
        return str(self)

    def conflicts_with(self, other):
        """Returns True if this requirement conflicts with another `Requirement`
        or `VersionedObject`."""
        if isinstance(other, Requirement):
            if (self.name_ != other.name_) or (self.range is None) \
                    or (other.range is None):
                return False
            elif self.conflict:
                return False if other.conflict \
                    else self.range_.issuperset(other.range_)
            elif other.conflict:
                return other.range_.issuperset(self.range_)
            else:
                return not self.range_.intersects(other.range_)
        else:  # VersionedObject
            if (self.name_ != other.name_) or (self.range is None):
                return False
            if self.conflict:
                return (other.version_ in self.range_)
            else:
                return (other.version_ not in self.range_)

    def merged(self, other):
        """Returns the merged result of two requirements.

        Two requirements can be in conflict and if so, this function returns
        None. For example, requests for "foo-4" and "foo-6" are in conflict,
        since both cannot be satisfied with a single version of foo.

        Some example successful requirements merges are:
        - "foo-3+" and "!foo-5+" == "foo-3+<5"
        - "foo-1" and "foo-1.5" == "foo-1.5"
        - "!foo-2" and "!foo-5" == "!foo-2|5"
        """
        if self.name_ != other.name_:
            return None  # cannot merge across object names

        def _r(r_):
            r = Requirement(None)
            r.name_ = r_.name_
            r.negate_ = r_.negate_
            r.conflict_ = r_.conflict_
            r.sep_ = r_.sep_
            return r

        if self.range is None:
            return other
        elif other.range is None:
            return self
        elif self.conflict:
            if other.conflict:
                r = _r(self)
                r.range_ = self.range_ | other.range_
                r.negate_ = (self.negate_ and other.negate_
                             and not r.range_.is_any())
                return r
            else:
                range_ = other.range - self.range
                if range_ is None:
                    return None
                else:
                    r = _r(other)
                    r.range_ = range_
                    return r
        elif other.conflict:
            range_ = self.range_ - other.range_
            if range_ is None:
                return None
            else:
                r = _r(self)
                r.range_ = range_
                return r
        else:
            range_ = self.range_ & other.range_
            if range_ is None:
                return None
            else:
                r = _r(self)
                r.range_ = range_
                return r

    def __eq__(self, other):
        return (isinstance(other, Requirement)
                and (self.name_ == other.name_)
                and (self.range_ == other.range_)
                and (self.conflict_ == other.conflict_))

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        if self._str is None:
            pre_str = '~' if self.negate_ else ('!' if self.conflict_ else '')
            range_str = ''
            sep_str = ''

            range_ = self.range_
            if self.negate_:
                range_ = ~range_ if range_ else VersionRange()

            if not range_.is_any():
                range_str = str(range_)
                if range_str[0] not in ('=', '<', '>'):
                    sep_str = self.sep_

            self._str = pre_str + self.name_ + sep_str + range_str
        return self._str


class RequirementList(_Common):
    """A list of requirements.

    This class takes a Requirement list and reduces it to the equivalent
    optimal form, merging any requirements for common objects. Order of objects
    is retained.
    """
    def __init__(self, requirements):
        """Create a RequirementList.

        Args:
            requirements: List of Requirement objects.
        """
        self.requirements_ = []
        self.conflict_ = None
        self.requirements_dict = {}
        self.names_ = set()
        self.conflict_names_ = set()

        for req in requirements:
            existing_req = self.requirements_dict.get(req.name)

            if existing_req is None:
                self.requirements_dict[req.name] = req
            else:
                merged_req = existing_req.merged(req)
                if merged_req is None:
                    self.conflict_ = (existing_req, req)
                    return
                else:
                    self.requirements_dict[req.name] = merged_req

        seen = set()

        # build optimised list, this intends to match original request order
        # as closely as possible
        for req in requirements:
            if req.name not in seen:
                seen.add(req.name)
                req_ = self.requirements_dict[req.name]
                self.requirements_.append(req_)

                if req_.conflict:
                    self.conflict_names_.add(req.name)
                else:
                    self.names_.add(req.name)

    @property
    def requirements(self):
        """Returns optimised list of requirements, or None if there are
        conflicts.
        """
        return self.requirements_

    @property
    def conflict(self):
        """Get the requirement conflict, if any.

        Returns:
            None if there is no conflict, otherwise a 2-tuple containing the
            conflicting Requirement objects.
        """
        return self.conflict_

    @property
    def names(self):
        """Set of names of requirements, not including conflict requirements.
        """
        return self.names_

    @property
    def conflict_names(self):
        """Set of conflict requirement names."""
        return self.conflict_names_

    def __iter__(self):
        for requirement in (self.requirements_ or []):
            yield requirement

    def get(self, name):
        """Returns the Requirement for the given object, or None.
        """
        return self.requirements_dict.get(name)

    def __eq__(self, other):
        return (isinstance(other, RequirementList)
                and (self.requirements_ == other.requirements_)
                and (self.conflict_ == other.conflict_))

    def __str__(self):
        if self.conflict_:
            s1 = str(self.conflict_[0])
            s2 = str(self.conflict_[1])
            return "%s <--!--> %s" % (s1, s2)
        else:
            return ' '.join(str(x) for x in self.requirements_)
