"""
The dependency resolving module.

This gives direct access to the solver. You should use the resolve() function
in resolve.py instead, which will use cached data where possible to provide you
with a faster resolve.

See SOLVER.md for an in-depth description of how this module works.
"""
from __future__ import print_function
from rez.config import config
from rez.packages_ import iter_packages
from rez.package_repository import package_repo_stats
from rez.utils.logging_ import print_debug
from rez.utils.data_utils import cached_property
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.algorithms.cycles import find_cycle
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PackageFamilyNotFoundError, RezSystemError
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement, \
    RequirementList
from rez.vendor.enum import Enum
from rez.vendor.sortedcontainers.sortedset import SortedSet
from contextlib import contextmanager
import copy
import time
import sys
import os


# a hidden control for forcing to non-optimized solving mode. This is here as
# first port of call for narrowing down the cause of a solver bug if we see one
_force_unoptimised_solver = (os.getenv("_FORCE_REZ_UNOPTIMISED_SOLVER") == "1")


class VariantSelectMode(Enum):
    """Variant selection mode."""
    version_priority = 0
    intersection_priority = 1


class SolverStatus(Enum):
    """Enum to represent the current state of a solver instance.  The enum
    also includes a human readable description of what the state represents.
    """

    pending = ("The solve has not yet started.", )
    solved = ("The solve has completed successfully.", )
    exhausted = ("The current solve is exhausted and must be split to continue further.", )
    failed = ("The solve is not possible.", )
    cyclic = ("The solve contains a cycle.", )
    unsolved = ("The solve has started, but is not yet solved.", )

    def __init__(self, description):
        self.description = description


class SolverCallbackReturn(Enum):
    """Enum returned by the `callback` callable passed to a `Solver` instance.
    """
    keep_going = ("Continue the solve",)
    abort = ("Abort the solve",)
    fail = ("Stop the solve and set to most recent failure")


class _Printer(object):
    def __init__(self, verbosity, buf=None, suppress_passive=False):
        self.verbosity = verbosity
        self.buf = buf or sys.stdout
        self.suppress_passive = suppress_passive
        self.pending_sub = None
        self.pending_br = False
        self.last_pr = True

    def header(self, txt, *args):
        if self.verbosity:
            if self.verbosity > 2:
                self.pr()
                self.pr('-' * 80)
            self.pr(txt % args)
            if self.verbosity > 2:
                self.pr('-' * 80)

    def subheader(self, txt):
        if self.verbosity > 2:
            self.pending_sub = txt

    def __call__(self, txt, *args):
        if self.verbosity > 2:
            if self.pending_sub:
                if self.last_pr:
                    self.pr()
                self.pr(self.pending_sub)
                self.pending_sub = None
            elif self.pending_br:
                self.pr()

            self.pr(txt % args)
            self.last_pr = True
            self.pending_br = False

    def passive(self, txt, *args):
        if self.suppress_passive:
            return

        self(txt, *args)

    def br(self):
        self.pending_br = True

    def pr(self, txt='', *args):
        print(txt % args, file=self.buf)

    def __nonzero__(self):
        return self.verbosity


class SolverState(object):
    """Represent the current state of the solver instance for use with a
    callback.
    """
    def __init__(self, num_solves, num_fails, phase):
        self.num_solves = num_solves
        self.num_fails = num_fails
        self.phase = phase

    def __str__(self):
        return ("solve #%d (%d fails so far): %s"
                % (self.num_solves, self.num_fails, str(self.phase)))


class _Common(object):
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class Reduction(_Common):
    """A variant was removed because its dependencies conflicted with another
    scope in the current phase."""
    def __init__(self, name, version, variant_index, dependency,
                 conflicting_request):
        self.name = name
        self.version = version
        self.variant_index = variant_index
        self.dependency = dependency
        self.conflicting_request = conflicting_request

    def reducee_str(self):
        stmt = VersionedObject.construct(self.name, self.version)
        idx_str = "[]" if self.variant_index is None \
            else "[%d]" % self.variant_index
        return str(stmt) + idx_str

    def involved_requirements(self):
        range_ = VersionRange.from_version(self.version)
        req = Requirement.construct(self.name, range_)
        return [req, self.dependency, self.conflicting_request]

    def __eq__(self, other):
        return (self.name == other.name and
                self.version == other.version and
                self.variant_index == other.variant_index and
                self.dependency == other.dependency and
                self.conflicting_request == other.conflicting_request)

    def __str__(self):
        return "%s (dep(%s) <--!--> %s)" \
            % (self.reducee_str(), self.dependency, self.conflicting_request)


class DependencyConflict(_Common):
    """A common dependency shared by all variants in a scope, conflicted with
    another scope in the current phase."""
    def __init__(self, dependency, conflicting_request):
        """
        Args:
            dependency (`Requirement`): Merged requirement from a set of variants.
            conflicting_request (`Requirement`): The request they conflict with.
        """
        self.dependency = dependency
        self.conflicting_request = conflicting_request

    def __eq__(self, other):
        return (self.dependency == other.dependency) \
            and (self.conflicting_request == other.conflicting_request)

    def __str__(self):
        return "%s <--!--> %s" % (str(self.dependency),
                                  str(self.conflicting_request))


class FailureReason(_Common):
    def involved_requirements(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError


class TotalReduction(FailureReason):
    """All of a scope's variants were reduced away."""
    def __init__(self, reductions):
        self.reductions = reductions

    def involved_requirements(self):
        pkgs = []
        for red in self.reductions:
            pkgs.extend(red.involved_requirements())
        return pkgs

    def description(self):
        return "A package was completely reduced: %s" % str(self)

    def __eq__(self, other):
        return (self.reductions == other.reductions)

    def __str__(self):
        return ' '.join(("(%s)" % str(x)) for x in self.reductions)


class DependencyConflicts(FailureReason):
    """A common dependency in a scope conflicted with another scope in the
    current phase."""
    def __init__(self, conflicts):
        self.conflicts = conflicts

    def involved_requirements(self):
        pkgs = []
        for conflict in self.conflicts:
            pkgs.append(conflict.dependency)
            pkgs.append(conflict.conflicting_request)
        return pkgs

    def description(self):
        return "The following package conflicts occurred: %s" % str(self)

    def __eq__(self, other):
        return (self.conflicts == other.conflicts)

    def __str__(self):
        return ' '.join(("(%s)" % str(x)) for x in self.conflicts)


class Cycle(FailureReason):
    """The solve contains a cyclic dependency."""
    def __init__(self, packages):
        self.packages = packages

    def involved_requirements(self):
        pkgs = []
        for pkg in self.packages:
            range_ = VersionRange.from_version(pkg.version)
            stmt = Requirement.construct(pkg.name, range_)
            pkgs.append(stmt)
        return pkgs

    def description(self):
        return "A cyclic dependency was detected: %s" % str(self)

    def __eq__(self, other):
        return (self.packages == other.packages)

    def __str__(self):
        stmts = self.packages + self.packages[:1]
        return " --> ".join(map(str, stmts))


class PackageVariant(_Common):
    """A variant of a package.
    """
    def __init__(self, variant, building):
        """Create a package variant.

        Args:
            variant (`Variant`): Package variant.
            building (bool): True if a build is occurring.
        """
        self.variant = variant
        self.building = building

    @property
    def name(self):
        return self.variant.name

    @property
    def version(self):
        return self.variant.version

    @property
    def index(self):
        return self.variant.index

    @property
    def handle(self):
        return self.variant.handle.to_dict()

    @cached_property
    def requires_list(self):
        """
        It is important that this property is calculated lazily. Getting the
        'requires' attribute may trigger a package load, which may be avoided if
        this variant is reduced away before that happens.
        """
        requires = self.variant.get_requires(build_requires=self.building)
        reqlist = RequirementList(requires)

        if reqlist.conflict:
            raise ResolveError(
                "The package %s has an internal requirements conflict: %s"
                % (str(self), str(reqlist)))

        return reqlist

    @property
    def request_fams(self):
        return self.requires_list.names

    @property
    def conflict_request_fams(self):
        return self.requires_list.conflict_names

    def get(self, pkg_name):
        return self.requires_list.get(pkg_name)

    def __eq__(self, other):
        return (self.name == other.name
                and self.version == other.version
                and self.index == other.index)

    def __lt__(self, other):
        return (self.name < other.name
                and self.version < other.version
                and self.index < other.index)

    def __str__(self):
        stmt = VersionedObject.construct(self.name, self.version)
        idxstr = '' if self.index is None else str(self.index)
        return "%s[%s]" % (str(stmt), idxstr)


class _PackageEntry(object):
    """The variants in a package.

    Holds some extra state data, such as whether the variants are sorted.
    """
    def __init__(self, package, variants, solver):
        self.package = package
        self.variants = variants
        self.solver = solver
        self.sorted = False

    @property
    def version(self):
        return self.package.version

    def __len__(self):
        return len(self.variants)

    def split(self, nvariants):
        if nvariants >= len(self.variants):
            return None

        self.sort()
        entry = _PackageEntry(self.package, self.variants[:nvariants], self.solver)
        next_entry = _PackageEntry(self.package, self.variants[nvariants:], self.solver)
        entry.sorted = next_entry.sorted = True
        return entry, next_entry

    def sort(self):
        """Sort variants from most correct to consume, to least.

        Sort rules:

        version_priority:
        - sort by highest versions of packages shared with request;
        - THEN least number of additional packages added to solve;
        - THEN highest versions of additional packages;
        - THEN alphabetical on name of additional packages;
        - THEN variant index.

        intersection_priority:
        - sort by highest number of packages shared with request;
        - THEN sort according to version_priority

        Note:
            In theory 'variant.index' should never factor into the sort unless
            two variants are identical (which shouldn't happen) - this is just
            here as a safety measure so that sorting is guaranteed repeatable
            regardless.
        """
        if self.sorted:
            return

        def key(variant):
            requested_key = []
            names = set()

            for i, request in enumerate(self.solver.request_list):
                if not request.conflict:
                    req = variant.requires_list.get(request.name)
                    if req is not None:
                        requested_key.append((-i, req.range))
                        names.add(req.name)

            additional_key = []
            for request in variant.requires_list:
                if not request.conflict and request.name not in names:
                    additional_key.append((request.range, request.name))

            if (VariantSelectMode[config.variant_select_mode] ==
                    VariantSelectMode.version_priority):
                k = (requested_key,
                     -len(additional_key),
                     additional_key,
                     variant.index)
            else:  # VariantSelectMode.intersection_priority
                k = (len(requested_key),
                     requested_key,
                     -len(additional_key),
                     additional_key,
                     variant.index)

            return k

        self.variants.sort(key=key, reverse=True)
        self.sorted = True


class _PackageVariantList(_Common):
    """A list of package variants, loaded lazily.
    """
    def __init__(self, package_name, solver):
        self.package_name = package_name
        self.solver = solver

        # note: we do not apply package filters here, because doing so might
        # cause package loads (eg, timestamp rules). We only apply filters
        # during an intersection, which minimises the amount of filtering.
        #
        self.entries = []

        for package in iter_packages(self.package_name,
                                     paths=self.solver.package_paths):
            package.set_context(solver.context)
            self.entries.append([package, False])

        if not self.entries:
            raise PackageFamilyNotFoundError(
                "package family not found: %s (searched: %s)"
                % (package_name, "; ".join(self.solver.package_paths)))

    def get_intersection(self, range_):
        """Get a list of variants that intersect with the given range.

        Args:
            range_ (`VersionRange`): Package version range.

        Returns:
            List of `_PackageEntry` objects.
        """
        result = []

        for entry in self.entries:
            package, value = entry

            if value is None:
                continue  # package was blocked by package filters

            if package.version not in range_:
                continue

            if isinstance(value, list):
                variants = value
                entry_ = _PackageEntry(package, variants, self.solver)
                result.append(entry_)
                continue

            # apply package filter
            if self.solver.package_filter:
                rule = self.solver.package_filter.excludes(package)
                if rule:
                    if config.debug_package_exclusions:
                        print_debug("Package '%s' was excluded by rule '%s'"
                                    % (package.qualified_name, str(rule)))
                    entry[1] = None
                    continue

            # expand package entry into list of variants
            if self.solver.package_load_callback:
                self.solver.package_load_callback(package)

            variants_ = []
            for var in package.iter_variants():
                variant = PackageVariant(var, self.solver.building)
                variants_.append(variant)

            entry[1] = variants_
            entry_ = _PackageEntry(package, variants_, self.solver)
            result.append(entry_)

        return result or None

    def dump(self):
        print(self.package_name)

        for package, value in self.entries:
            print(str(package.version))
            if value is None:
                print("    [FILTERED]")
            elif isinstance(value, list):
                variants = value
                for variant in variants:
                    print("    %s" % str(variant))
            else:
                print("    %s" % str(package))

    def __str__(self):
        strs = []

        for package, value in self.entries:
            if value is None:
                continue
            elif isinstance(value, list):
                variants = value
                val_str = ','.join(str(x) for x in variants)
            else:
                val_str = str(package)

            strs.append(val_str)

        return "%s[%s]" % (self.package_name, ' '.join(strs))


class _PackageVariantSlice(_Common):
    """A subset of a variant list, but with more dependency-related info."""
    def __init__(self, package_name, entries, solver):
        """
        Args:
            entries (list of `_PackageEntry`): result of
                _PackageVariantList.get_intersection().
        """
        self.solver = solver
        self.package_name = package_name
        self.entries = entries
        self.extracted_fams = set()
        self.been_reduced_by = set()
        self.been_intersected_with = set()
        self.sorted = False

        # calculated on demand
        self._len = None
        self._range = None
        self._fam_requires = None
        self._common_fams = None

    @property
    def pr(self):
        return self.solver.pr

    @property
    def range_(self):
        if self._range is None:
            versions = (x.version for x in self.entries)
            self._range = VersionRange.from_versions(versions)
        return self._range

    @property
    def fam_requires(self):
        self._update_fam_info()
        return self._fam_requires

    @property
    def common_fams(self):
        self._update_fam_info()
        return self._common_fams

    @property
    def extractable(self):
        """True if there are possible remaining extractions."""
        return not self.extracted_fams.issuperset(self.common_fams)

    @property
    def first_variant(self):
        entry = self.entries[0]
        entry.sort()
        return entry.variants[0]

    def iter_variants(self):
        for entry in self.entries:
            for variant in entry.variants:
                yield variant

    def intersect(self, range_):
        self.solver.intersection_broad_tests_count += 1

        """Remove variants whose version fall outside of the given range."""
        if range_.is_any():
            return self

        if self.solver.optimised:
            if range_ in self.been_intersected_with:
                return self

        if self.pr:
            self.pr.passive("intersecting %s wrt range '%s'...", self, range_)

        self.solver.intersection_tests_count += 1

        with self.solver.timed(self.solver.intersection_time):
            # this is faster than iter_intersecting :(
            entries = [x for x in self.entries if x.version in range_]

        if not entries:
            return None
        elif len(entries) < len(self.entries):
            copy_ = self._copy(entries)
            copy_.been_intersected_with.add(range_)
            return copy_
        else:
            self.been_intersected_with.add(range_)
            return self

    def reduce_by(self, package_request):
        """Remove variants whos dependencies conflict with the given package
        request.

        Returns:
            (VariantSlice, [Reduction]) tuple, where slice may be None if all
            variants were reduced.
        """
        if self.pr:
            reqstr = _short_req_str(package_request)
            self.pr.passive("reducing %s wrt %s...", self, reqstr)

        if self.solver.optimised:
            if package_request in self.been_reduced_by:
                return (self, [])

        if (package_request.range is None) or \
                (package_request.name not in self.fam_requires):
            return (self, [])

        with self.solver.timed(self.solver.reduction_time):
            return self._reduce_by(package_request)

    def _reduce_by(self, package_request):
        self.solver.reduction_tests_count += 1

        entries = []
        reductions = []
        conflict_tests = {}

        def _conflicts(req_):
            # cache conflict tests, since variants often share similar requirements
            req_s = str(req)
            result = conflict_tests.get(req_s)
            if result is None:
                result = req_.conflicts_with(package_request)
                conflict_tests[req_s] = result
            return result

        for entry in self.entries:
            new_variants = []

            for variant in entry.variants:
                req = variant.get(package_request.name)
                if req and _conflicts(req):
                    red = Reduction(name=variant.name,
                                    version=variant.version,
                                    variant_index=variant.index,
                                    dependency=req,
                                    conflicting_request=package_request)

                    reductions.append(red)
                    if self.pr:
                        self.pr("removed %s", red)
                else:
                    new_variants.append(variant)

            n = len(new_variants)
            if n < len(entry):
                if n == 0:
                    continue
                entry = _PackageEntry(entry.package, new_variants, self.solver)

            entries.append(entry)

        if not entries:
            return (None, reductions)
        elif reductions:
            copy_ = self._copy(new_entries=entries)
            copy_.been_reduced_by.add(package_request)
            return (copy_, reductions)
        else:
            self.been_reduced_by.add(package_request)
            return (self, [])

    def extract(self):
        """Extract a common dependency.

        Note that conflict dependencies are never extracted, they are always
        resolved via reduction.
        """
        if not self.extractable:
            return self, None

        extractable = self.common_fams - self.extracted_fams

        # the sort is necessary to ensure solves are deterministic
        fam = sorted(extractable)[0]

        last_range = None
        ranges = set()

        for variant in self.iter_variants():
            req = variant.get(fam)
            if req.range != last_range:  # will match often, avoids set search
                ranges.add(req.range)
                last_range = req.range

        slice_ = copy.copy(self)
        slice_.extracted_fams = self.extracted_fams | set([fam])

        ranges = list(ranges)
        range_ = ranges[0].union(ranges[1:])
        common_req = Requirement.construct(fam, range_)
        return slice_, common_req

    def split(self):
        """Split the slice.

        Returns:
            (`_PackageVariantSlice`, `_PackageVariantSlice`) tuple, where the
            first is the preferred slice.
        """

        # We sort here in the split in order to sort as late as possible.
        # Because splits usually happen after intersections/reductions, this
        # means there can be less entries to sort.
        #
        self.sort_versions()

        def _split(i_entry, n_variants, common_fams=None):
            # perform a split at a specific point
            result = self.entries[i_entry].split(n_variants)

            if result:
                entry, next_entry = result
                entries = self.entries[:i_entry] + [entry]
                next_entries = [next_entry] + self.entries[i_entry + 1:]
            else:
                entries = self.entries[:i_entry + 1]
                next_entries = self.entries[i_entry + 1:]

            slice_ = self._copy(entries)
            next_slice = self._copy(next_entries)

            if self.pr:
                if common_fams:
                    if len(common_fams) == 1:
                        reason_str = next(iter(common_fams))
                    else:
                        reason_str = ", ".join(common_fams)
                else:
                    reason_str = "first variant"
                self.pr("split (reason: %s) %s into %s and %s",
                        reason_str, self, slice_, next_slice)

            return slice_, next_slice

        # determine if we need to find first variant without common dependency
        if len(self) > 2:
            fams = self.first_variant.request_fams - self.extracted_fams
        else:
            fams = None

        if not fams:
            # trivial case, split on first variant
            return _split(0, 1)

        # find split point - first variant with no dependency shared with previous
        prev = None
        for i, entry in enumerate(self.entries):
            # sort the variants. This is done here in order to do the sort as
            # late as possible, simply to avoid the cost.
            entry.sort()

            for j, variant in enumerate(entry.variants):
                fams = fams & variant.request_fams
                if not fams:
                    return _split(*prev)

                prev = (i, j + 1, fams)

        # should never get here - it's only possible if there's a common
        # dependency, but if there's a common dependency, split() should never
        # have been called.
        raise RezSystemError(
            "Unexpected solver error: common family(s) still in slice being "
            "split: slice: %s, family(s): %s" % (self, str(fams)))

    def sort_versions(self):
        """Sort entries by version.

        The order is typically descending, but package order functions can
        change this.
        """
        if self.sorted:
            return

        for orderer in (self.solver.package_orderers or []):
            entries = orderer.reorder(self.entries, key=lambda x: x.package)
            if entries is not None:
                self.entries = entries
                self.sorted = True

                if self.pr:
                    self.pr("sorted: %s packages: %s", self.package_name, repr(orderer))
                return

        # default ordering is version descending
        self.entries = sorted(self.entries, key=lambda x: x.version, reverse=True)
        self.sorted = True

        if self.pr:
            self.pr("sorted: %s packages: version descending", self.package_name)

    def dump(self):
        print(self.package_name)
        print('\n'.join(map(str, self.iter_variants())))

    def _copy(self, new_entries):
        slice_ = _PackageVariantSlice(package_name=self.package_name,
                                      entries=new_entries,
                                      solver=self.solver)

        slice_.sorted = self.sorted
        slice_.been_reduced_by = self.been_reduced_by.copy()
        slice_.been_intersected_with = self.been_intersected_with.copy()
        return slice_

    def _update_fam_info(self):
        if self._common_fams is not None:
            return

        self._common_fams = set(self.first_variant.request_fams)
        self._fam_requires = set()

        for variant in self.iter_variants():
            self._common_fams &= variant.request_fams
            self._fam_requires |= (variant.request_fams |
                                   variant.conflict_request_fams)

    def __len__(self):
        if self._len is None:
            self._len = 0
            for entry in self.entries:
                self._len += len(entry)

        return self._len

    def __str__(self):
        """
        foo[2..6(3:4)]* means, 3 versions, 4 variants in 2..6, and at least one
            family can still be extracted.
        foo[2..6(2)] means, 2 versions in 2..6.
        [foo==2[1,2]] means, 1st and 2nd variants of exact version foo-2.
        [foo==2]* means, exact version foo-2, families still to extract.
        [foo==2] means a resolved package (no variants in the package).
        [foo=2[0]] means a resolved package (zeroeth variant).
        """
        nvariants = len(self)
        nversions = len(self.entries)

        if nvariants == 1:
            variant = self.first_variant
            s_idx = "" if variant.index is None else "[%d]" % variant.index
            s = "[%s==%s%s]" % (self.package_name, str(variant.version), s_idx)
        elif nversions == 1:
            entry = self.entries[0]
            indexes = sorted([x.index for x in entry.variants])
            s_idx = ','.join(str(x) for x in indexes)
            verstr = str(entry.version)
            s = "[%s==%s[%s]]" % (self.package_name, verstr, s_idx)
        else:
            verstr = "%d" % nvariants if (nversions == nvariants) \
                else "%d:%d" % (nversions, nvariants)

            span = self.range_.span()
            s = "%s[%s(%s)]" % (self.package_name, str(span), verstr)

        strextr = '*' if self.extractable else ''
        return s + strextr


class PackageVariantCache(object):
    def __init__(self, solver):
        self.solver = solver
        self.variant_lists = {}  # {package-name: _PackageVariantList}

    def get_variant_slice(self, package_name, range_):
        """Get a list of variants from the cache.

        Args:
            package_name (str): Name of package.
            range_ (`VersionRange`): Package version range.

        Returns:
            `_PackageVariantSlice` object.
        """
        variant_list = self.variant_lists.get(package_name)

        if variant_list is None:
            variant_list = _PackageVariantList(package_name, self.solver)
            self.variant_lists[package_name] = variant_list

        entries = variant_list.get_intersection(range_)
        if not entries:
            return None

        slice_ = _PackageVariantSlice(package_name,
                                      entries=entries,
                                      solver=self.solver)
        return slice_


class _PackageScope(_Common):
    """Contains possible solutions for a package, such as a list of variants,
    or a conflict range. As the resolve progresses, package scopes are narrowed
    down.
    """
    def __init__(self, package_request, solver):
        self.package_name = package_request.name
        self.solver = solver
        self.variant_slice = None
        self.pr = solver.pr

        if package_request.conflict:
            self.package_request = package_request
        else:
            self.variant_slice = solver._get_variant_slice(
                package_request.name, package_request.range)

            if self.variant_slice is None:
                req = Requirement.construct(package_request.name,
                                            package_request.range)
                raise PackageNotFoundError("Package could not be found: %s"
                                           % str(req))
            self._update()

    @property
    def is_conflict(self):
        return self.package_request and self.package_request.conflict

    def intersect(self, range_):
        """Intersect this scope with a package range.

        Returns:
            A new copy of this scope, with variants whos version fall outside
            of the given range removed. If there were no removals, self is
            returned. If all variants were removed, None is returned.
        """
        new_slice = None

        if self.package_request.conflict:
            if self.package_request.range is None:
                new_slice = self.solver._get_variant_slice(
                    self.package_name, range_)
            else:
                new_range = range_ - self.package_request.range
                if new_range is not None:
                    new_slice = self.solver._get_variant_slice(
                        self.package_name, new_range)
        else:
            new_slice = self.variant_slice.intersect(range_)

        # intersection reduced the scope to nothing
        if new_slice is None:
            if self.pr:
                self.pr("%s intersected with range '%s' resulted in no packages",
                        self, range_)
            return None

        # intersection narrowed the scope
        if new_slice is not self.variant_slice:
            scope = self._copy(new_slice)
            if self.pr:
                self.pr("%s was intersected to %s by range '%s'",
                        self, scope, range_)
            return scope

        # intersection did not change the scope
        return self

    def reduce_by(self, package_request):
        """Reduce this scope wrt a package request.

        Returns:
            A (_PackageScope, [Reduction]) tuple, where the scope is a new
            scope copy with reductions applied, or self if there were no
            reductions, or None if the scope was completely reduced.
        """
        self.solver.reduction_broad_tests_count += 1

        if self.package_request.conflict:
            # conflict scopes don't reduce. Instead, other scopes will be
            # reduced against a conflict scope.
            return (self, [])

        # perform the reduction
        new_slice, reductions = self.variant_slice.reduce_by(package_request)

        # there was total reduction
        if new_slice is None:
            self.solver.reductions_count += 1

            if self.pr:
                reqstr = _short_req_str(package_request)
                self.pr("%s was reduced to nothing by %s", self, reqstr)
                self.pr.br()

            return (None, reductions)

        # there was some reduction
        if new_slice is not self.variant_slice:
            self.solver.reductions_count += 1
            scope = self._copy(new_slice)

            if self.pr:
                reqstr = _short_req_str(package_request)
                self.pr("%s was reduced to %s by %s", self, scope, reqstr)
                self.pr.br()
            return (scope, reductions)

        # there was no reduction
        return (self, [])

    def extract(self):
        """Extract a common dependency.

        Returns:
            A (_PackageScope, Requirement) tuple, containing the new scope copy
            with the extraction, and the extracted package range. If no package
            was extracted, then (self,None) is returned.
        """
        if not self.package_request.conflict:
            new_slice, package_request = self.variant_slice.extract()
            if package_request:
                assert(new_slice is not self.variant_slice)
                scope = copy.copy(self)
                scope.variant_slice = new_slice
                if self.pr:
                    self.pr("extracted %s from %s", package_request, self)
                return (scope, package_request)

        return (self, None)

    def split(self):
        """Split the scope.

        Returns:
            A (_PackageScope, _PackageScope) tuple, where the first scope is
            guaranteed to have a common dependency. Or None, if splitting is
            not applicable to this scope.
        """
        if self.package_request.conflict or (len(self.variant_slice) == 1):
            return None
        else:
            r = self.variant_slice.split()
            if r is None:
                return None
            else:
                slice, next_slice = r
                scope = self._copy(slice)
                next_scope = self._copy(next_slice)
                return (scope, next_scope)

    def _copy(self, new_slice):
        scope = copy.copy(self)
        scope.variant_slice = new_slice
        scope._update()
        return scope

    def _is_solved(self):
        return bool(self.package_request.conflict) \
            or ((len(self.variant_slice) == 1)
                and (not self.variant_slice.extractable))

    def _get_solved_variant(self):
        if (not self.package_request.conflict) \
                and (len(self.variant_slice) == 1) \
                and (not self.variant_slice.extractable):
            return self.variant_slice.first_variant
        else:
            return None

    def _update(self):
        if self.variant_slice is not None:
            self.package_request = Requirement.construct(
                self.package_name, self.variant_slice.range_)

    def __str__(self):
        if self.variant_slice is None:
            return str(self.package_request)
        else:
            return str(self.variant_slice)


def _get_dependency_order(g, node_list):
    """Return list of nodes as close as possible to the ordering in node_list,
    but with child nodes earlier in the list than parents."""
    access_ = accessibility(g)
    deps = dict((k, set(v) - set([k])) for k, v in access_.items())
    nodes = node_list + list(set(g.nodes()) - set(node_list))
    ordered_nodes = []

    while nodes:
        n_ = nodes[0]
        n_deps = deps.get(n_)
        if (n_ in ordered_nodes) or (n_deps is None):
            nodes = nodes[1:]
            continue

        moved = False
        for i, n in enumerate(nodes[1:]):
            if n in n_deps:
                nodes = [nodes[i + 1]] + nodes[:i + 1] + nodes[i + 2:]
                moved = True
                break

        if not moved:
            ordered_nodes.append(n_)
            nodes = nodes[1:]

    return ordered_nodes


class _ResolvePhase(_Common):
    """A resolve phase contains a full copy of the resolve state, and runs the
    resolve algorithm until no further action can be taken without 'selecting'
    a sub-range of some package. When this selection occurs, a phase splits
    into two - one with the selected subrange, and one without - and these two
    new phases replace this phase on the solver's phase stack.

    If the resolve phase gets to a point where every package scope is solved,
    then the entire resolve is considered to be solved.
    """
    def __init__(self, solver):
        self.solver = solver
        self.failure_reason = None
        self.extractions = {}
        self.status = SolverStatus.pending

        self.scopes = []
        for package_request in self.solver.request_list:
            scope = _PackageScope(package_request, solver=solver)
            self.scopes.append(scope)

        # only so an initial reduction across all scopes happens in a new phase
        self.changed_scopes_i = set(range(len(self.scopes)))

    @property
    def pr(self):
        return self.solver.pr

    def solve(self):
        """Attempt to solve the phase."""
        if self.status != SolverStatus.pending:
            return self

        scopes = self.scopes[:]
        failure_reason = None
        extractions = {}

        changed_scopes_i = self.changed_scopes_i.copy()

        def _create_phase(status=None):
            phase = copy.copy(self)
            phase.scopes = scopes
            phase.failure_reason = failure_reason
            phase.extractions = extractions
            phase.changed_scopes_i = set()

            if status is None:
                phase.status = (SolverStatus.solved if phase._is_solved()
                                else SolverStatus.exhausted)
            else:
                phase.status = status
            return phase

        # iteratively reduce until no more reductions possible
        while True:
            prev_num_scopes = len(scopes)
            widened_scopes_i = set()

            # iteratively extract until no more extractions possible
            while True:
                self.pr.subheader("EXTRACTING:")
                extracted_requests = []

                # perform all possible extractions
                with self.solver.timed(self.solver.extraction_time):
                    for i in range(len(scopes)):
                        while True:
                            scope_, extracted_request = scopes[i].extract()

                            if extracted_request:
                                extracted_requests.append(extracted_request)
                                k = (scopes[i].package_name, extracted_request.name)
                                extractions[k] = extracted_request
                                self.solver.extractions_count += 1
                                scopes[i] = scope_
                            else:
                                break

                if not extracted_requests:
                    break

                # simplify extractions (there may be overlaps)
                self.pr.subheader("MERGE-EXTRACTIONS:")
                extracted_requests = RequirementList(extracted_requests)

                if extracted_requests.conflict:  # extractions are in conflict
                    req1, req2 = extracted_requests.conflict
                    conflict = DependencyConflict(req1, req2)
                    failure_reason = DependencyConflicts([conflict])
                    return _create_phase(SolverStatus.failed)
                elif self.pr:
                    self.pr("merged extractions: %s", extracted_requests)

                # intersect extracted requests with current scopes
                self.pr.subheader("INTERSECTING:")
                req_fams = []

                with self.solver.timed(self.solver.intersection_test_time):
                    for i, scope in enumerate(scopes):
                        extracted_req = extracted_requests.get(scope.package_name)

                        if extracted_req is None:
                            continue

                        # perform the intersection
                        scope_ = scope.intersect(extracted_req.range)

                        req_fams.append(extracted_req.name)

                        if scope_ is None:
                            # the scope conflicted with the extraction
                            conflict = DependencyConflict(
                                extracted_req, scope.package_request)
                            failure_reason = DependencyConflicts([conflict])
                            return _create_phase(SolverStatus.failed)

                        if scope_ is not scope:
                            # the scope was narrowed because it intersected
                            # with an extraction
                            scopes[i] = scope_
                            changed_scopes_i.add(i)
                            self.solver.intersections_count += 1

                            # if the intersection caused a conflict scope to turn
                            # into a non-conflict scope, then it has to be reduced
                            # against all other scopes.
                            #
                            # In the very common case, if a scope changes then it
                            # has been narrowed, so there is no need to reduce it
                            # against other unchanged scopes. In this case however,
                            # the scope actually widens! For eg, '~foo-1' may be
                            # intersected with 'foo' to become 'foo-1', which might
                            # then reduce against existing scopes.
                            #
                            if scope.is_conflict and not scope_.is_conflict:
                                widened_scopes_i.add(i)

                # add new scopes
                new_extracted_reqs = [
                    x for x in extracted_requests.requirements
                    if x.name not in req_fams]

                if new_extracted_reqs:
                    self.pr.subheader("ADDING:")
                    #n = len(scopes)

                    for req in new_extracted_reqs:
                        scope = _PackageScope(req, solver=self.solver)
                        scopes.append(scope)
                        if self.pr:
                            self.pr("added %s", scope)

            num_scopes = len(scopes)

            # no further reductions to do
            if (num_scopes == prev_num_scopes) \
                    and not changed_scopes_i \
                    and not widened_scopes_i:
                break

            # iteratively reduce until no more reductions possible
            self.pr.subheader("REDUCING:")

            if not self.solver.optimised:
                # force reductions across all scopes
                changed_scopes_i = set(range(num_scopes))
                prev_num_scopes = num_scopes

            # create set of pending reductions from the list of changed scopes
            # and list of added scopes. We use a sorted set because the solver
            # must be deterministic, ie its behavior must always be the same for
            # a given solve. A normal set does not guarantee order.
            #
            # Each item is an (x, y) tuple, where scope[x] will reduce by
            # scope[y].package_request.
            #
            pending_reducts = SortedSet()
            all_scopes_i = range(num_scopes)
            added_scopes_i = range(prev_num_scopes, num_scopes)

            for x in range(prev_num_scopes):
                # existing scopes must reduce against changed scopes
                for y in changed_scopes_i:
                    if x != y:
                        pending_reducts.add((x, y))

                # existing scopes must reduce against newly added scopes
                for y in added_scopes_i:
                    pending_reducts.add((x, y))

            # newly added scopes must reduce against all other scopes
            for x in added_scopes_i:
                for y in all_scopes_i:
                    if x != y:
                        pending_reducts.add((x, y))

            # 'widened' scopes (see earlier comment in this func) must reduce
            # against all other scopes
            for x in widened_scopes_i:
                for y in all_scopes_i:
                    if x != y:
                        pending_reducts.add((x, y))

            # iteratively reduce until there are no more pending reductions.
            # Note that if a scope is reduced, then other scopes need to reduce
            # against it once again.
            with self.solver.timed(self.solver.reduction_test_time):
                while pending_reducts:
                    x, y = pending_reducts.pop()

                    new_scope, reductions = scopes[x].reduce_by(
                        scopes[y].package_request)

                    if new_scope is None:
                        failure_reason = TotalReduction(reductions)
                        return _create_phase(SolverStatus.failed)

                    elif new_scope is not scopes[x]:
                        scopes[x] = new_scope

                        # other scopes need to reduce against x again
                        for j in all_scopes_i:
                            if j != x:
                                pending_reducts.add((j, x))

            changed_scopes_i = set()

        return _create_phase()

    def finalise(self):
        """Remove conflict requests, detect cyclic dependencies, and reorder
        packages wrt dependency and then request order.

        Returns:
            A new copy of the phase with conflict requests removed and packages
            correctly ordered; or, if cyclic dependencies were detected, a new
            phase marked as cyclic.
        """
        assert(self._is_solved())
        g = self._get_minimal_graph()
        scopes = dict((x.package_name, x) for x in self.scopes
                      if not x.package_request.conflict)

        # check for cyclic dependencies
        fam_cycle = find_cycle(g)
        if fam_cycle:
            cycle = []
            for fam in fam_cycle:
                scope = scopes[fam]
                variant = scope._get_solved_variant()
                stmt = VersionedObject.construct(fam, variant.version)
                cycle.append(stmt)

            phase = copy.copy(self)
            phase.scopes = scopes.values()
            phase.failure_reason = Cycle(cycle)
            phase.status = SolverStatus.cyclic
            return phase

        # reorder wrt dependencies, keeping original request order where possible
        fams = [x.name for x in self.solver.request_list]
        ordered_fams = _get_dependency_order(g, fams)

        scopes_ = []
        for fam in ordered_fams:
            scope = scopes[fam]
            if not scope.package_request.conflict:
                scopes_.append(scope)

        phase = copy.copy(self)
        phase.scopes = scopes_
        return phase

    def split(self):
        """Split the phase.

        When a phase is exhausted, it gets split into a pair of phases to be
        further solved. The split happens like so:
        1) Select the first unsolved package scope.
        2) Find some common dependency in the first N variants of the scope.
        3) Split the scope into two: [:N] and [N:].
        4) Create two copies of the phase, containing each half of the split
           scope.

        The result of this split is that we have a new phase (the first phase),
        which contains a package scope with a common dependency. This
        dependency can now be intersected with the current resolve, thus
        progressing it.

        Returns:
            A 2-tuple of _ResolvePhase objects, where the first phase is the
            best contender for resolving.
        """
        assert(self.status == SolverStatus.exhausted)

        scopes = []
        next_scopes = []
        split_i = None

        for i, scope in enumerate(self.scopes):
            if split_i is None:
                r = scope.split()
                if r is not None:
                    scope_, next_scope = r
                    scopes.append(scope_)
                    next_scopes.append(next_scope)
                    split_i = i
                    continue

            scopes.append(scope)
            next_scopes.append(scope)

        assert split_i is not None

        phase = copy.copy(self)
        phase.scopes = scopes
        phase.status = SolverStatus.pending
        phase.changed_scopes_i = set([split_i])

        # because a scope was narrowed by a split, other scopes need to be
        # reduced against it
        #for i in range(len(phase.scopes)):
        #    if i != split_i:
        #        phase.pending_reducts.add((i, split_i))

        next_phase = copy.copy(phase)
        next_phase.scopes = next_scopes
        return (phase, next_phase)

    def get_graph(self):
        """Get the resolve graph.

        The resolve graph shows what packages were resolved, and the
        relationships between them. A failed phase also has a graph, which
        will shows the conflict(s) that caused the resolve to fail.

        Returns:
            A pygraph.digraph object.
        """
        g = digraph()
        scopes = dict((x.package_name, x) for x in self.scopes)
        failure_nodes = set()
        request_nodes = {}  # (request, node_id)
        scope_nodes = {}  # (package_name, node_id)

        # -- graph creation basics

        node_color = "#F6F6F6"
        request_color = "#FFFFAA"
        solved_color = "#AAFFAA"
        node_fontsize = 10
        counter = [1]

        def _uid():
            id_ = counter[0]
            counter[0] += 1
            return "_%d" % id_

        def _add_edge(id1, id2, arrowsize=0.5):
            e = (id1, id2)
            if g.has_edge(e):
                g.del_edge(e)
            g.add_edge(e)
            g.add_edge_attribute(e, ("arrowsize", str(arrowsize)))
            return e

        def _add_extraction_merge_edge(id1, id2):
            e = _add_edge(id1, id2, 1)
            g.add_edge_attribute(e, ("arrowhead", "odot"))

        def _add_conflict_edge(id1, id2):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, "CONFLICT")
            g.add_edge_attribute(e, ("style", "bold"))
            g.add_edge_attribute(e, ("color", "red"))
            g.add_edge_attribute(e, ("fontcolor", "red"))

        def _add_cycle_edge(id1, id2):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, "CYCLE")
            g.add_edge_attribute(e, ("style", "bold"))
            g.add_edge_attribute(e, ("color", "red"))
            g.add_edge_attribute(e, ("fontcolor", "red"))

        def _add_reduct_edge(id1, id2, label):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, label)
            g.add_edge_attribute(e, ("fontsize", node_fontsize))

        def _add_node(label, color, style):
            attrs = [("label", label),
                     ("fontsize", node_fontsize),
                     ("fillcolor", color),
                     ("style", '"%s"' % style)]
            id_ = _uid()
            g.add_node(id_, attrs=attrs)
            return id_

        def _add_request_node(request, initial_request=False):
            id_ = request_nodes.get(request)
            if id_ is not None:
                return id_

            label = str(request)
            if initial_request:
                color = request_color
            else:
                color = node_color

            id_ = _add_node(label, color, "filled,dashed")
            request_nodes[request] = id_
            return id_

        def _add_scope_node(scope):
            id_ = scope_nodes.get(scope.package_name)
            if id_ is not None:
                return id_

            variant = scope._get_solved_variant()
            if variant:
                label = str(variant)
                color = solved_color
                style = "filled"
            elif scope.is_conflict:
                label = str(scope)
                color = node_color
                style = "filled,dashed"
            else:
                label = str(scope)
                color = node_color
                style = "filled"

            id_ = _add_node(label, color, style)
            scope_nodes[scope.package_name] = id_
            return id_

        def _add_reduct_node(request):
            return _add_node(str(request), node_color, "filled,dashed")

        # -- generate the graph

        # create initial request nodes
        for request in self.solver.request_list:
            _add_request_node(request, True)

        # create scope nodes
        for scope in self.scopes:
            if scope.is_conflict:
                id1 = request_nodes.get(scope.package_request)
                if id1 is not None:
                    # special case - a scope that matches an initial conflict request,
                    # we switch nodes so the request node becomes a scope node
                    scope_nodes[scope.package_name] = id1
                    del request_nodes[scope.package_request]
                    continue

            _add_scope_node(scope)

        # create (initial request -> scope) edges
        for request in self.solver.request_list:
            id1 = request_nodes.get(request)
            if id1 is not None:
                id2 = scope_nodes.get(request.name)
                if id2 is not None:
                    _add_edge(id1, id2)

        # for solved scopes, create (scope -> requirement) edge
        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                id1 = scope_nodes[scope.package_name]

                for request in variant.requires_list.requirements:
                    id2 = _add_request_node(request)
                    _add_edge(id1, id2)

        # add extractions
        for (src_fam, _), dest_req in self.extractions.items():
            id1 = scope_nodes.get(src_fam)
            if id1 is not None:
                id2 = _add_request_node(dest_req)
                _add_edge(id1, id2)

        # add extraction intersections
        extracted_fams = set(x[1] for x in self.extractions.keys())
        for fam in extracted_fams:
            requests = [v for k, v in self.extractions.items() if k[1] == fam]
            if len(requests) > 1:
                reqlist = RequirementList(requests)
                if not reqlist.conflict:
                    merged_request = reqlist.get(fam)
                    for request in requests:
                        if merged_request != request:
                            id1 = _add_request_node(request)
                            id2 = _add_request_node(merged_request)
                            _add_extraction_merge_edge(id1, id2)

        # add conflicts
        fr = self.failure_reason
        if fr:
            if isinstance(fr, DependencyConflicts):
                for conflict in fr.conflicts:
                    id1 = _add_request_node(conflict.dependency)
                    id2 = scope_nodes.get(conflict.conflicting_request.name)
                    if id2 is None:
                        id2 = _add_request_node(conflict.conflicting_request)
                    _add_conflict_edge(id1, id2)

                    failure_nodes.add(id1)
                    failure_nodes.add(id2)
            elif isinstance(fr, TotalReduction):
                if len(fr.reductions) == 1:
                    # special case - singular total reduction
                    reduct = fr.reductions[0]
                    id1 = scope_nodes[reduct.name]
                    id2 = _add_request_node(reduct.dependency)
                    id3 = scope_nodes[reduct.conflicting_request.name]
                    _add_edge(id1, id2)
                    _add_conflict_edge(id2, id3)

                    failure_nodes.add(id1)
                    failure_nodes.add(id2)
                    failure_nodes.add(id3)
                else:
                    for reduct in fr.reductions:
                        id1 = scope_nodes[reduct.name]
                        id2 = _add_reduct_node(reduct.dependency)
                        id3 = scope_nodes[reduct.conflicting_request.name]
                        _add_reduct_edge(id1, id2, reduct.reducee_str())
                        _add_conflict_edge(id2, id3)

                        failure_nodes.add(id1)
                        failure_nodes.add(id2)
                        failure_nodes.add(id3)
            elif isinstance(fr, Cycle):
                for i, pkg in enumerate(fr.packages):
                    id1 = scope_nodes[pkg.name]
                    failure_nodes.add(id1)
                    pkg2 = fr.packages[(i + 1) % len(fr.packages)]
                    id2 = scope_nodes[pkg2.name]
                    _add_cycle_edge(id1, id2)

        # connect leaf-node requests to a matching scope, if any
        for request, id1 in request_nodes.items():
            if not g.neighbors(id1):  # leaf node
                id2 = scope_nodes.get(request.name)
                if id2 is not None:
                    scope = scopes.get(request.name)
                    if not request.conflicts_with(scope.package_request):
                        _add_edge(id1, id2)

        # prune nodes not related to failure
        if self.solver.prune_unfailed and failure_nodes:
            access_dict = accessibility(g)
            del_nodes = set()

            for n, access_nodes in access_dict.items():
                if not (set(access_nodes) & failure_nodes):
                    del_nodes.add(n)

            for n in del_nodes:
                g.del_node(n)

        return g

    def _get_minimal_graph(self):
        if not self._is_solved():
            return None

        nodes = set()
        edges = set()
        scopes = dict((x.package_name, x) for x in self.scopes)

        for scope in scopes.values():
            variant = scope._get_solved_variant()
            if variant:
                nodes.add(variant.name)
                for req in variant.requires_list.requirements:
                    if not req.conflict:
                        scope_ = scopes.get(req.name)
                        if scope_:
                            variant_ = scope_._get_solved_variant()
                            if variant_:
                                nodes.add(variant_.name)
                                edges.add((variant.name, variant_.name))

        g = digraph()
        g.add_nodes(nodes)
        for e in edges:
            g.add_edge(e)

        return g

    def _is_solved(self):
        for scope in self.scopes:
            if not scope._is_solved():
                return False
        return True

    def _get_solved_variants(self):
        variants = []
        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                variants.append(variant)

        return variants

    def __str__(self):
        return ' '.join(str(x) for x in self.scopes)


class Solver(_Common):
    """Solver.

    A package solver takes a list of package requests (the 'request'), then
    runs a resolve algorithm in order to determine the 'resolve' - the list of
    non-conflicting packages that include all dependencies.
    """
    max_verbosity = 3

    def __init__(self, package_requests, package_paths, context=None,
                 package_filter=None, package_orderers=None, callback=None,
                 building=False, optimised=True, verbosity=0, buf=None,
                 package_load_callback=None, prune_unfailed=True,
                 suppress_passive=False, print_stats=False):
        """Create a Solver.

        Args:
            package_requests: List of Requirement objects representing the
                request.
            package_paths: List of paths to search for pkgs.
            context (`ResolvedContext`): Context this solver is used within, if
                any. This is needed in a solve if any packages contain late
                binding package attributes that need access to context info.
            package_filter (`PackageFilterBase`): Filter for excluding packages.
            package_orderers (list of `PackageOrder`): Custom package ordering.
            building: True if we're resolving for a build.
            optimised: Run the solver in optimised mode. This is only ever set
                to False for testing purposes.
            callback: If not None, this callable will be called after each
                solve step. It is passed a `SolverState` object. It must return
                a 2-tuple:
                - `SolverCallbackReturn` object indicating what to do next;
                - str: Reason for solve abort, ignored if solve not aborted.
                If the callable returns `SolverCallbackReturn.fail`, but there
                has not been a failure, the solver will ignore the callback and
                continue on with the solve.
            package_load_callback: If not None, this callable will be called
                prior to each package being loaded. It is passed a single
                `Package` object.
            prune_unfailed (bool): If the solve failed, and `prune_unfailed` is
                True, any packages unrelated to the conflict are removed from
                the graph.
            suppress_passive (bool): If True, don't print debugging info that
                has had no effect on the solve. This argument only has an
                effect if `verbosity` > 2.
            print_stats (bool): If true, print advanced solver stats at the end.
        """
        self.package_paths = package_paths
        self.package_filter = package_filter
        self.package_orderers = package_orderers
        self.callback = callback
        self.prune_unfailed = prune_unfailed
        self.package_load_callback = package_load_callback
        self.building = building
        self.request_list = None
        self.context = context

        self.pr = _Printer(verbosity, buf=buf, suppress_passive=suppress_passive)
        self.print_stats = print_stats
        self.buf = buf

        if _force_unoptimised_solver:
            self.optimised = False
        else:
            self.optimised = optimised

        self.non_conflict_package_requests = [x for x in package_requests
                                              if not x.conflict]

        self.phase_stack = None
        self.failed_phase_list = None
        self.abort_reason = None
        self.callback_return = None
        self.depth_counts = None
        self.solve_begun = None
        self.solve_time = None
        self.load_time = None

        # advanced solve metrics
        self.solve_count = 0
        self.extractions_count = 0
        self.intersections_count = 0
        self.intersection_tests_count = 0
        self.intersection_broad_tests_count = 0
        self.reductions_count = 0
        self.reduction_tests_count = 0
        self.reduction_broad_tests_count = 0

        self.extraction_time = [0.0]
        self.intersection_time = [0.0]
        self.intersection_test_time = [0.0]
        self.reduction_time = [0.0]
        self.reduction_test_time = [0.0]

        self._init()

        self.package_cache = PackageVariantCache(self)

        # merge the request
        if self.pr:
            self.pr("request: %s", ' '.join(map(str, package_requests)))
        self.request_list = RequirementList(package_requests)

        if self.request_list.conflict:
            req1, req2 = self.request_list.conflict
            if self.pr:
                self.pr("conflict in request: %s <--!--> %s", req1, req2)

            conflict = DependencyConflict(req1, req2)
            phase = _ResolvePhase(solver=self)
            phase.failure_reason = DependencyConflicts([conflict])
            phase.status = SolverStatus.failed
            self._push_phase(phase)
            return
        elif self.pr:
            s = ' '.join(map(str, self.request_list.requirements))
            self.pr("merged request: %s", s)

        # create the initial phase
        phase = _ResolvePhase(solver=self)
        self._push_phase(phase)

    @contextmanager
    def timed(self, target):
        t = time.time()
        yield
        secs = time.time() - t
        target[0] += secs

    @property
    def status(self):
        """Return the current status of the solve.

        Returns:
          SolverStatus: Enum representation of the state of the solver.
        """
        if self.request_list.conflict:
            return SolverStatus.failed

        if self.callback_return == SolverCallbackReturn.fail:
            # the solve has failed because a callback has nominated the most
            # recent failure as the reason.
            return SolverStatus.failed

        st = self.phase_stack[-1].status
        if st == SolverStatus.cyclic:
            return SolverStatus.failed
        elif len(self.phase_stack) > 1:
            if st == SolverStatus.solved:
                return SolverStatus.solved
            else:
                return SolverStatus.unsolved
        elif st in (SolverStatus.pending, SolverStatus.exhausted):
            return SolverStatus.unsolved
        else:
            return st

    @property
    def num_solves(self):
        """Return the number of solve steps that have been executed."""
        return self.solve_count

    @property
    def num_fails(self):
        """Return the number of failed solve steps that have been executed.
        Note that num_solves is inclusive of failures."""
        n = len(self.failed_phase_list)
        if self.phase_stack[-1].status in (SolverStatus.failed, SolverStatus.cyclic):
            n += 1
        return n

    @property
    def cyclic_fail(self):
        """Return True if the solve failed due to a cycle, False otherwise."""
        return (self.phase_stack[-1].status == SolverStatus.cyclic)

    @property
    def resolved_packages(self):
        """Return a list of PackageVariant objects, or None if the resolve did
        not complete or was unsuccessful.
        """
        if (self.status != SolverStatus.solved):
            return None

        final_phase = self.phase_stack[-1]
        return final_phase._get_solved_variants()

    def reset(self):
        """Reset the solver, removing any current solve."""
        if not self.request_list.conflict:
            phase = _ResolvePhase(self.request_list.requirements, solver=self)
            self.pr("resetting...")
            self._init()
            self._push_phase(phase)

    def solve(self):
        """Attempt to solve the request.
        """
        if self.solve_begun:
            raise ResolveError("cannot run solve() on a solve that has "
                               "already been started")

        t1 = time.time()
        pt1 = package_repo_stats.package_load_time

        # iteratively solve phases
        while self.status == SolverStatus.unsolved:
            self.solve_step()
            if self.status == SolverStatus.unsolved and not self._do_callback():
                break

        self.load_time = package_repo_stats.package_load_time - pt1
        self.solve_time = time.time() - t1

        # print stats
        if self.pr.verbosity > 2:
            from pprint import pformat
            self.pr.subheader("SOLVE STATS:")
            self.pr(pformat(self.solve_stats))

        elif self.print_stats:
            from pprint import pformat
            data = {"solve_stats": self.solve_stats}
            print(pformat(data), file=(self.buf or sys.stdout))

    @property
    def solve_stats(self):
        extraction_stats = {
            "extraction_time": self.extraction_time[0],
            "num_extractions": self.extractions_count
        }

        intersection_stats = {
            "num_intersections": self.intersections_count,
            "num_intersection_tests": self.intersection_tests_count,
            "num_intersection_broad_tests": self.intersection_broad_tests_count,
            "intersection_time": self.intersection_time[0],
            "intersection_test_time": self.intersection_test_time[0]
        }

        reduction_stats = {
            "num_reductions": self.reductions_count,
            "num_reduction_tests": self.reduction_tests_count,
            "num_reduction_broad_tests": self.reduction_broad_tests_count,
            "reduction_time": self.reduction_time[0],
            "reduction_test_time": self.reduction_test_time[0]
        }

        global_stats = {
            "num_solves": self.num_solves,
            "num_fails": self.num_fails,
            "solve_time": self.solve_time,
            "load_time": self.load_time
        }

        return {
            "global": global_stats,
            "extractions": extraction_stats,
            "intersections": intersection_stats,
            "reductions": reduction_stats
        }

    def solve_step(self):
        """Perform a single solve step.
        """
        self.solve_begun = True
        if self.status != SolverStatus.unsolved:
            return

        if self.pr:
            self.pr.header("SOLVE #%d (%d fails so far)...",
                           self.solve_count + 1, self.num_fails)

        phase = self._pop_phase()

        if phase.status == SolverStatus.failed:  # a previously failed phase
            self.pr("discarded failed phase, fetching previous unsolved phase...")
            self.failed_phase_list.append(phase)
            phase = self._pop_phase()

        if phase.status == SolverStatus.exhausted:
            self.pr.subheader("SPLITTING:")
            phase, next_phase = phase.split()
            self._push_phase(next_phase)
            if self.pr:
                self.pr("new phase: %s", phase)

        new_phase = phase.solve()
        self.solve_count += 1

        if new_phase.status == SolverStatus.failed:
            self.pr.subheader("FAILED:")
            self._push_phase(new_phase)
            if self.pr and len(self.phase_stack) == 1:
                self.pr.header("FAIL: there is no solution")

        elif new_phase.status == SolverStatus.solved:
            # solved, but there may be cyclic dependencies
            self.pr.subheader("SOLVED:")
            final_phase = new_phase.finalise()
            self._push_phase(final_phase)

            if self.pr:
                if final_phase.status == SolverStatus.cyclic:
                    self.pr.header("FAIL: a cycle was detected")
                else:
                    self.pr.header("SUCCESS")

        else:
            self.pr.subheader("EXHAUSTED:")
            assert(new_phase.status == SolverStatus.exhausted)
            self._push_phase(new_phase)

    def failure_reason(self, failure_index=None):
        """Get the reason for a failure.

        Args:
            failure_index: Index of the fail to return the graph for (can be
                negative). If None, the most appropriate failure is chosen
                according to these rules:
                - If the fail is cyclic, the most recent fail (the one containing
                  the cycle) is used;
                - If a callback has caused a failure, the most recent fail is used;
                - Otherwise, the first fail is used.

        Returns:
            A `FailureReason` subclass instance describing the failure.
        """
        phase, _ = self._get_failed_phase(failure_index)
        return phase.failure_reason

    def failure_description(self, failure_index=None):
        """Get a description of the failure.

        This differs from `failure_reason` - in some cases, such as when a
        callback forces a failure, there is more information in the description
        than there is from `failure_reason`.
        """
        _, description = self._get_failed_phase(failure_index)
        return description

    def failure_packages(self, failure_index=None):
        """Get packages involved in a failure.

        Args:
            failure_index: See `failure_reason`.

        Returns:
            A list of Requirement objects.
        """
        phase, _ = self._get_failed_phase(failure_index)
        fr = phase.failure_reason
        return fr.involved_requirements() if fr else None

    def get_graph(self):
        """Returns the most recent solve graph.

        This gives a graph showing the latest state of the solve. The specific
        graph returned depends on the solve status. When status is:
        unsolved: latest unsolved graph is returned;
        solved:   final solved graph is returned;
        failed:   most appropriate failure graph is returned (see `failure_reason`);
        cyclic:   last failure is returned (contains cycle).

        Returns:
            A pygraph.digraph object.
        """
        st = self.status
        if st in (SolverStatus.solved, SolverStatus.unsolved):
            phase = self._latest_nonfailed_phase()
            return phase.get_graph()
        else:
            return self.get_fail_graph()

    def get_fail_graph(self, failure_index=None):
        """Returns a graph showing a solve failure.

        Args:
            failure_index: See `failure_reason`

        Returns:
            A pygraph.digraph object.
        """
        phase, _ = self._get_failed_phase(failure_index)
        return phase.get_graph()

    def dump(self):
        """Print a formatted summary of the current solve state."""
        from rez.utils.formatting import columnise

        rows = []
        for i, phase in enumerate(self.phase_stack):
            rows.append((self._depth_label(i), phase.status, str(phase)))

        print("status: %s (%s)" % (self.status.name, self.status.description))
        print("initial request: %s" % str(self.request_list))
        print()
        print("solve stack:")
        print('\n'.join(columnise(rows)))

        if self.failed_phase_list:
            rows = []
            for i, phase in enumerate(self.failed_phase_list):
                rows.append(("#%d" % i, phase.status, str(phase)))
            print()
            print("previous failures:")
            print('\n'.join(columnise(rows)))

    def _init(self):
        self.phase_stack = []
        self.failed_phase_list = []
        self.depth_counts = {}
        self.solve_time = 0.0
        self.load_time = 0.0
        self.solve_begun = False

        # advanced solve stats
        self.solve_count = 0
        self.extractions_count = 0
        self.intersections_count = 0
        self.intersection_tests_count = 0
        self.intersection_broad_tests_count = 0
        self.reductions_count = 0
        self.reduction_tests_count = 0
        self.reduction_broad_tests_count = 0

        self.extraction_time = [0.0]
        self.intersection_time = [0.0]
        self.intersection_test_time = [0.0]
        self.reduction_time = [0.0]
        self.reduction_test_time = [0.0]

    def _latest_nonfailed_phase(self):
        if self.status == SolverStatus.failed:
            return None

        for phase in reversed(self.phase_stack):
            if phase.status not in (SolverStatus.failed, SolverStatus.cyclic):
                return phase
        assert(False)  # should never get here

    def _do_callback(self):
        keep_going = True
        if self.callback:
            phase = self._latest_nonfailed_phase()
            if phase:
                s = SolverState(self.num_solves, self.num_fails, phase)
                value, abort_reason = self.callback(s)
                if value == SolverCallbackReturn.abort:
                    self.pr("solve aborted: %s", abort_reason)
                    self.abort_reason = abort_reason
                    keep_going = False
                elif value == SolverCallbackReturn.fail:
                    if self.num_fails:
                        self.abort_reason = abort_reason
                        self.pr("solve failed: %s", abort_reason)
                        self.callback_return = value
                        keep_going = False

        return keep_going

    def _get_variant_slice(self, package_name, range_):
        slice_ = self.package_cache.get_variant_slice(
            package_name=package_name, range_=range_)

        return slice_

    def _push_phase(self, phase):
        depth = len(self.phase_stack)
        count = self.depth_counts.get(depth, -1) + 1
        self.depth_counts[depth] = count
        self.phase_stack.append(phase)

        if self.pr:
            dlabel = self._depth_label()
            self.pr("pushed %s: %s", dlabel, phase)

    def _pop_phase(self):
        dlabel = self._depth_label()
        phase = self.phase_stack.pop()
        if self.pr:
            self.pr("popped %s: %s", dlabel, phase)
        return phase

    def _get_failed_phase(self, index=None):
        # returns (phase, fail_description)
        prepend_abort_reason = False
        fails = self.failed_phase_list
        st = self.phase_stack[-1].status
        if st in (SolverStatus.failed, SolverStatus.cyclic):
            fails = fails + self.phase_stack[-1:]

        if index is None:
            if st == SolverStatus.cyclic:
                index = -1
            elif self.callback_return == SolverCallbackReturn.fail:
                prepend_abort_reason = True
                index = -1
            else:
                index = 0

        try:
            phase = fails[index]
        except IndexError:
            raise IndexError("failure index out of range")

        fail_description = phase.failure_reason.description()
        if prepend_abort_reason and self.abort_reason:
            fail_description = "%s:\n%s" % (self.abort_reason, fail_description)

        return phase, fail_description

    def _depth_label(self, depth=None):
        if depth is None:
            depth = len(self.phase_stack) - 1
        count = self.depth_counts[depth]
        return "{%d,%d}" % (depth,count)

    def __str__(self):
        return "%s %s %s" % (self.status,
                             self._depth_label(),
                             str(self.phase_stack[-1]))


def _short_req_str(package_request):
    """print shortened version of '==X|==Y|==Z' ranged requests."""
    if not package_request.conflict:
        versions = package_request.range.to_versions()
        if versions and len(versions) == len(package_request.range) \
                and len(versions) > 1:
            return "%s-%s(%d)" % (package_request.name,
                                  str(package_request.range.span()),
                                  len(versions))
    return str(package_request)


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
