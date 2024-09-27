# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
The dependency resolving module.

This gives direct access to the solver. You should use the resolve() function
in resolve.py instead, which will use cached data where possible to provide you
with a faster resolve.

See SOLVER.md for an in-depth description of how this module works.
"""
from __future__ import annotations

from rez.config import config
from rez.packages import iter_packages, Package, Variant
from rez.package_repository import package_repo_stats
from rez.utils.logging_ import print_debug
from rez.utils.data_utils import cached_property
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.algorithms.cycles import find_cycle
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PackageFamilyNotFoundError, RezSystemError
from rez.version import Version, VersionRange
from rez.version import VersionedObject, Requirement, RequirementList
from rez.utils.typing import SupportsLessThan, Protocol
from contextlib import contextmanager
from enum import Enum
from itertools import product, chain
from typing import Any, Callable, Generator, Iterator, TypeVar, TYPE_CHECKING
import copy
import time
import sys
import os

if TYPE_CHECKING:
    from rez.resolved_context import ResolvedContext
    from rez.package_filter import PackageFilterBase
    from rez.package_order import PackageOrder


T = TypeVar("T")


class SupportsWrite(Protocol):
    def write(self, __s: str) -> object:
        pass


# a hidden control for forcing to non-optimized solving mode. This is here as
# first port of call for narrowing down the cause of a solver bug if we see one
#
_force_unoptimised_solver = (os.getenv("_FORCE_REZ_UNOPTIMISED_SOLVER") == "1")


# the 'solver version' is an internal version number that changes if the
# behaviour of the solver changes in a way that potentially changes the result
# of a solve.
#
# Solves are deterministic - given a known request and set of package repositories,
# the result should always be the same. However, bugfixes or intentional changes
# to solver behaviour might change the solve result. In  this case, there's a good
# chance that the benchmark.yaml workflow will fail, since it expects the same
# results as the previous workflow run.
#
# If the benchmark.yaml workflow fails, and you determine that the solver behaviour
# change is intentional and expected, then you need to update this version. The
# workflow will then succeed on its next run, because it will skip the check
# against the previous results, if the solver version differs.
#
SOLVER_VERSION = 2


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


class SolverCallbackReturn(Enum):
    """Enum returned by the `callback` callable passed to a `Solver` instance.
    """
    keep_going = ("Continue the solve",)
    abort = ("Abort the solve",)
    fail = ("Stop the solve and set to most recent failure")


class _Printer(object):
    def __init__(self, verbosity, buf: SupportsWrite | None = None, suppress_passive: bool = False):
        self.verbosity = verbosity
        self.buf = buf or sys.stdout
        self.suppress_passive = suppress_passive
        self.pending_sub: str | None = None
        self.pending_br = False
        self.last_pr = True

    def header(self, txt: str, *args: Any) -> None:
        if self.verbosity:
            if self.verbosity > 2:
                self.pr()
                self.pr('-' * 80)
            self.pr(txt % args)
            if self.verbosity > 2:
                self.pr('-' * 80)

    def subheader(self, txt: str) -> None:
        if self.verbosity > 2:
            self.pending_sub = txt

    def __call__(self, txt: str, *args: Any) -> None:
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

    def passive(self, txt: str, *args: Any) -> None:
        if self.suppress_passive:
            return

        self(txt, *args)

    def br(self) -> None:
        self.pending_br = True

    def pr(self, txt: str = '', *args: Any) -> None:
        print(txt % args, file=self.buf)

    def __bool__(self) -> bool:
        return self.verbosity > 0


class SolverState(object):
    """Represent the current state of the solver instance for use with a
    callback.
    """
    def __init__(self, num_solves: int, num_fails: int, phase: _ResolvePhase):
        self.num_solves = num_solves
        self.num_fails = num_fails
        self.phase = phase

    def __str__(self) -> str:
        return ("solve #%d (%d fails so far): %s"
                % (self.num_solves, self.num_fails, str(self.phase)))


class _Common(object):
    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, str(self))


class Reduction(_Common):
    """A variant was removed because its dependencies conflicted with another
    scope in the current phase."""
    def __init__(self, name: str, version, variant_index: int | None, dependency: Requirement,
                 conflicting_request: Requirement):
        self.name = name
        self.version = version
        self.variant_index = variant_index
        self.dependency = dependency
        self.conflicting_request = conflicting_request

    def reducee_str(self) -> str:
        stmt = VersionedObject.construct(self.name, self.version)
        idx_str = "[]" if self.variant_index is None \
            else "[%d]" % self.variant_index
        return str(stmt) + idx_str

    def involved_requirements(self) -> list[Requirement]:
        range_ = VersionRange.from_version(self.version)
        req = Requirement.construct(self.name, range_)
        return [req, self.dependency, self.conflicting_request]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Reduction):
            return NotImplemented

        return (self.name == other.name
                and self.version == other.version
                and self.variant_index == other.variant_index
                and self.dependency == other.dependency
                and self.conflicting_request == other.conflicting_request)

    def __str__(self) -> str:
        return "%s (dep(%s) <--!--> %s)" \
            % (self.reducee_str(), self.dependency, self.conflicting_request)


class DependencyConflict(_Common):
    """A common dependency shared by all variants in a scope, conflicted with
    another scope in the current phase."""
    def __init__(self, dependency: Requirement, conflicting_request: Requirement):
        """
        Args:
            dependency (`Requirement`): Merged requirement from a set of variants.
            conflicting_request (`Requirement`): The request they conflict with.
        """
        self.dependency = dependency
        self.conflicting_request = conflicting_request

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DependencyConflict):
            return NotImplemented

        return (self.dependency == other.dependency) \
            and (self.conflicting_request == other.conflicting_request)

    def __str__(self) -> str:
        return "%s <--!--> %s" % (str(self.dependency),
                                  str(self.conflicting_request))


class FailureReason(_Common):
    def involved_requirements(self) -> list[Requirement]:
        return []

    def description(self) -> str:
        return ""


class TotalReduction(FailureReason):
    """All of a scope's variants were reduced away."""
    def __init__(self, reductions: list[Reduction]):
        self.reductions = reductions

    def involved_requirements(self) -> list[Requirement]:
        pkgs = []
        for red in self.reductions:
            pkgs.extend(red.involved_requirements())
        return pkgs

    def description(self) -> str:
        return "A package was completely reduced: %s" % str(self)

    def __eq__(self, other):
        return (self.reductions == other.reductions)

    def __str__(self) -> str:
        return ' '.join(("(%s)" % str(x)) for x in self.reductions)


class DependencyConflicts(FailureReason):
    """A common dependency in a scope conflicted with another scope in the
    current phase."""
    def __init__(self, conflicts: list[DependencyConflict]):
        self.conflicts = conflicts

    def involved_requirements(self) -> list[Requirement]:
        pkgs = []
        for conflict in self.conflicts:
            pkgs.append(conflict.dependency)
            pkgs.append(conflict.conflicting_request)
        return pkgs

    def description(self) -> str:
        return "The following package conflicts occurred: %s" % str(self)

    def __eq__(self, other) -> bool:
        return (self.conflicts == other.conflicts)

    def __str__(self) -> str:
        return ' '.join(("(%s)" % str(x)) for x in self.conflicts)


class Cycle(FailureReason):
    """The solve contains a cyclic dependency."""
    def __init__(self, packages: list[VersionedObject]):
        self.packages = packages

    def involved_requirements(self) -> list[Requirement]:
        pkgs = []
        for pkg in self.packages:
            range_ = VersionRange.from_version(pkg.version)
            stmt = Requirement.construct(pkg.name, range_)
            pkgs.append(stmt)
        return pkgs

    def description(self) -> str:
        return "A cyclic dependency was detected: %s" % str(self)

    def __eq__(self, other) -> bool:
        return (self.packages == other.packages)

    def __str__(self) -> str:
        stmts = self.packages + self.packages[:1]
        return " --> ".join(map(str, stmts))


class PackageVariant(_Common):
    """A variant of a package.
    """
    def __init__(self, variant: Variant, building: bool):
        """Create a package variant.

        Args:
            variant (`Variant`): Package variant.
            building (bool): True if a build is occurring.
        """
        self.variant = variant
        self.building = building

    @property
    def name(self) -> str:
        return self.variant.name

    @property
    def version(self) -> Version:
        return self.variant.version

    @property
    def index(self) -> int | None:
        return self.variant.index

    @property
    def handle(self) -> dict[str, Any]:
        return self.variant.handle.to_dict()

    @cached_property
    def requires_list(self) -> RequirementList:
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
    def request_fams(self) -> set[str]:
        return self.requires_list.names

    @property
    def conflict_request_fams(self) -> set[str]:
        return self.requires_list.conflict_names

    def get(self, pkg_name: str) -> Requirement | None:
        return self.requires_list.get(pkg_name)

    def __eq__(self, other) -> bool:
        return (
            self.name == other.name
            and self.version == other.version
            and self.index == other.index
        )

    def __lt__(self, other) -> bool:
        return (
            self.name < other.name
            and self.version < other.version
            and self.index < other.index
        )

    def __str__(self) -> str:
        stmt = VersionedObject.construct(self.name, self.version)
        idxstr = '' if self.index is None else str(self.index)
        return "%s[%s]" % (str(stmt), idxstr)


class _PackageEntry(object):
    """The variants in a package.

    Holds some extra state data, such as whether the variants are sorted.
    """
    def __init__(self, package: Package, variants: list[PackageVariant], solver: Solver):
        self.package = package
        self.variants = variants
        self.solver = solver
        self.sorted = False

    @property
    def version(self) -> Version:
        return self.package.version

    def __len__(self) -> int:
        return len(self.variants)

    def split(self, nvariants: int) -> tuple[_PackageEntry, _PackageEntry] | None:
        if nvariants >= len(self.variants):
            return None

        self.sort()
        entry = _PackageEntry(self.package, self.variants[:nvariants], self.solver)
        next_entry = _PackageEntry(self.package, self.variants[nvariants:], self.solver)
        entry.sorted = next_entry.sorted = True
        return entry, next_entry

    def sort(self) -> None:
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
        from rez.package_order import get_orderer

        if self.sorted:
            return

        def key(variant: PackageVariant) -> tuple[SupportsLessThan, ...]:
            requested_key = []
            names = set()

            for i, request in enumerate(self.solver.request_list):
                if not request.conflict:
                    req = variant.requires_list.get(request.name)
                    if req is not None:
                        orderer = get_orderer(req.name, orderers=self.solver.package_orderers or {})
                        range_key = orderer.sort_key(req.name, req.range)
                        requested_key.append((-i, range_key))
                        names.add(req.name)

            additional_key = []
            for request in variant.requires_list:
                if not request.conflict and request.name not in names:
                    orderer = get_orderer(request.name, orderers=self.solver.package_orderers)
                    range_key = orderer.sort_key(request.name, request.range)
                    additional_key.append((range_key, request.name))

            if (VariantSelectMode[config.variant_select_mode] == VariantSelectMode.version_priority):
                return (requested_key,
                        -len(additional_key),
                        additional_key,
                        # None does not support proper sorting, so fall back to int
                        variant.index or -1)
            else:  # VariantSelectMode.intersection_priority
                return (len(requested_key),
                        requested_key,
                        -len(additional_key),
                        additional_key,
                        # None does not support proper sorting, so fall back to int
                        variant.index or -1)

        self.variants.sort(key=key, reverse=True)
        self.sorted = True


class _PackageVariantList(_Common):
    """A list of package variants, loaded lazily.
    """
    def __init__(self, package_name: str, solver: Solver):
        self.package_name = package_name
        self.solver = solver

        # note: we do not apply package filters here, because doing so might
        # cause package loads (eg, timestamp rules). We only apply filters
        # during an intersection, which minimises the amount of filtering.
        #
        self.entries: list[list[Any]] = []

        for package in iter_packages(self.package_name,
                                     paths=self.solver.package_paths):
            package.set_context(solver.context)
            self.entries.append([package, False])

        if not self.entries:
            raise PackageFamilyNotFoundError(
                "package family not found: %s (searched: %s)"
                % (package_name, "; ".join(self.solver.package_paths)))

    def get_intersection(self, range_: VersionRange) -> list[_PackageEntry] | None:
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

    def dump(self) -> None:
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

    def __str__(self) -> str:
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
    def __init__(self, package_name: str, entries: list[_PackageEntry], solver: Solver):
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
        self._len: int | None = None
        self._range: VersionRange | None = None
        self._fam_requires: set[str] | None = None
        self._common_fams: set[str] | None = None

    @property
    def pr(self) -> _Printer:
        return self.solver.pr

    @property
    def range_(self) -> VersionRange:
        if self._range is None:
            versions = (x.version for x in self.entries)
            self._range = VersionRange.from_versions(versions)
        return self._range

    @property
    def fam_requires(self) -> set[str]:
        self._update_fam_info()
        assert self._fam_requires is not None
        return self._fam_requires

    @property
    def common_fams(self) -> set[str]:
        self._update_fam_info()
        assert self._common_fams is not None
        return self._common_fams

    @property
    def extractable(self) -> bool:
        """True if there are possible remaining extractions."""
        return not self.extracted_fams.issuperset(self.common_fams)

    @property
    def first_variant(self) -> PackageVariant:
        entry = self.entries[0]
        entry.sort()
        return entry.variants[0]

    def iter_variants(self) -> Iterator[PackageVariant]:
        for entry in self.entries:
            for variant in entry.variants:
                yield variant

    def intersect(self, range_: VersionRange) -> _PackageVariantSlice | None:
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

    def reduce_by(self, package_request: Requirement) -> tuple[_PackageVariantSlice | None, list[Reduction]]:
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

    def _reduce_by(self, package_request: Requirement) -> tuple[_PackageVariantSlice | None, list[Reduction]]:
        self.solver.reduction_tests_count += 1

        entries = []
        reductions = []
        conflict_tests = {}

        def _conflicts(req_: Requirement):
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

    def extract(self) -> tuple[_PackageVariantSlice, Requirement | None]:
        """Extract a common dependency.

        Note that conflict dependencies are never extracted, they are always
        resolved via reduction.
        """
        if not self.extractable:
            return self, None

        extractable = self.common_fams - self.extracted_fams

        # the sort is necessary to ensure solves are deterministic
        fam = sorted(extractable)[0]

        last_range: VersionRange | None = None
        ranges = set()

        for variant in self.iter_variants():
            req = variant.get(fam)
            assert req is not None
            if req.range != last_range:  # will match often, avoids set search
                ranges.add(req.range)
                last_range = req.range

        slice_ = copy.copy(self)
        slice_.extracted_fams = self.extracted_fams | set([fam])

        ranges = list(ranges)
        range_ = ranges[0].union(ranges[1:])
        common_req = Requirement.construct(fam, range_)
        return slice_, common_req

    def split(self) -> tuple[_PackageVariantSlice, _PackageVariantSlice]:
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

        def _split(i_entry: int, n_variants: int, common_fams=None):
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
            self.entries[0].sort()
            return _split(0, 1)

        # find split point - first variant with no dependency shared with previous
        prev: tuple[int, int, set[str]] | None = None
        for i, entry in enumerate(self.entries):
            # sort the variants. This is done here in order to do the sort as
            # late as possible, simply to avoid the cost.
            entry.sort()

            for j, variant in enumerate(entry.variants):
                fams = fams & variant.request_fams
                if not fams:
                    assert prev is not None
                    return _split(*prev)

                prev = (i, j + 1, fams)

        # should never get here - it's only possible if there's a common
        # dependency, but if there's a common dependency, split() should never
        # have been called.
        raise RezSystemError(
            "Unexpected solver error: common family(s) still in slice being "
            "split: slice: %s, family(s): %s" % (self, str(fams)))

    def sort_versions(self) -> None:
        """Sort entries by version.

        The order is typically descending, but package order functions can
        change this.
        """
        from rez.package_order import get_orderer

        if self.sorted:
            return

        orderer = get_orderer(self.package_name, orderers=self.solver.package_orderers or {})

        def sort_key(entry: _PackageEntry) -> SupportsLessThan:
            return orderer.sort_key(entry.package.name, entry.version)

        self.entries = sorted(self.entries, key=sort_key, reverse=True)
        self.sorted = True

        if self.pr:
            self.pr("sorted: %s packages: %s", self.package_name, repr(orderer))

    def dump(self) -> None:
        print(self.package_name)
        print('\n'.join(map(str, self.iter_variants())))

    def _copy(self, new_entries: list[_PackageEntry]) -> _PackageVariantSlice:
        slice_ = _PackageVariantSlice(package_name=self.package_name,
                                      entries=new_entries,
                                      solver=self.solver)

        slice_.sorted = self.sorted
        slice_.been_reduced_by = self.been_reduced_by.copy()
        slice_.been_intersected_with = self.been_intersected_with.copy()
        return slice_

    def _update_fam_info(self) -> None:
        if self._common_fams is not None:
            return

        self._common_fams = set(self.first_variant.request_fams)
        self._fam_requires = set()

        for variant in self.iter_variants():
            self._common_fams &= variant.request_fams
            self._fam_requires |= (variant.request_fams
                                   | variant.conflict_request_fams)

    def __len__(self) -> int:
        if self._len is None:
            self._len = 0
            for entry in self.entries:
                self._len += len(entry)

        return self._len

    def __str__(self) -> str:
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
            # we expect all variants to have a non-None index, but filter to satisfy mypy
            indexes = sorted([x.index for x in entry.variants if x.index is not None])
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
    def __init__(self, solver: Solver):
        self.solver = solver
        self.variant_lists: dict[str, _PackageVariantList] = {}  # {package-name: _PackageVariantList}

    def get_variant_slice(self, package_name: str, range_: VersionRange) -> _PackageVariantSlice | None:
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
    def __init__(self, package_request: Requirement, solver: Solver):
        self.package_name = package_request.name
        self.solver = solver
        self.variant_slice = None
        self.pr = solver.pr
        self.is_ephemeral = (package_request.name.startswith('.'))

        if package_request.conflict or self.is_ephemeral:
            # these cases don't actually contain variants
            self.package_request = package_request
        else:
            self.variant_slice = solver._get_variant_slice(
                package_request.name, package_request.range)

            if self.variant_slice is None:
                req = Requirement.construct(package_request.name,
                                            package_request.range)
                raise PackageNotFoundError("Package could not be found: %s"
                                           % str(req))
            # This call to _update() will set self.package_request
            self._update()

    @property
    def is_conflict(self) -> bool:
        return bool(self.package_request and self.package_request.conflict)

    def intersect(self, range_: VersionRange) -> _PackageScope | None:
        """Intersect this scope with a package range.

        Returns:
            A new copy of this scope, with variants whos version fall outside
            of the given range removed. If there were no removals, self is
            returned. If all variants were removed, None is returned.
        """

        # ephemerals are just a range intersection
        if self.is_ephemeral:
            if self.is_conflict:
                intersect_range = range_ - self.package_request.range
            else:
                intersect_range = range_ & self.package_request.range

            if intersect_range is None:
                if self.pr:
                    self.pr(
                        "%s intersected with range '%s' resulted in conflict",
                        self, range_
                    )
                return None
            elif intersect_range == self.package_request.range:
                # intersection did not change the scope
                return self
            else:
                scope = copy.copy(self)
                scope.package_request = Requirement.construct(
                    self.package_name, intersect_range
                )

                if self.pr:
                    self.pr(
                        "%s was intersected to %s by range '%s'",
                        self, scope, range_
                    )
                return scope

        # typical case: slice or conflict
        new_slice = None

        if self.is_conflict:
            if self.package_request.range is None:
                new_slice = self.solver._get_variant_slice(
                    self.package_name, range_)
            else:
                new_range = range_ - self.package_request.range
                if new_range is not None:
                    new_slice = self.solver._get_variant_slice(
                        self.package_name, new_range)
        else:
            assert self.variant_slice is not None, \
                "variant_slice should always exist for non-conflicted non-ephemeral requests"
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

    def reduce_by(self, package_request: Requirement) -> tuple[_PackageScope | None, list[Reduction]]:
        """Reduce this scope wrt a package request.

        Returns:
            A (_PackageScope, [Reduction]) tuple, where the scope is a new
            scope copy with reductions applied, or self if there were no
            reductions, or None if the scope was completely reduced.
        """
        self.solver.reduction_broad_tests_count += 1

        # reduction of conflicts and ephemerals is nonsensical (they have no
        # variant list to reduce)
        if self.is_conflict or self.is_ephemeral:
            return (self, [])

        assert self.variant_slice is not None, \
            "variant_slice should always exist for non-conflicted non-ephemeral requests"

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

    def extract(self) -> tuple[_PackageScope, Requirement | None]:
        """Extract a common dependency.

        Returns:
            A (_PackageScope, Requirement) tuple, containing the new scope copy
            with the extraction, and the extracted package range. If no package
            was extracted, then (self,None) is returned.
        """

        # extraction is nonsensical for conflicts and ephemerals
        if self.is_conflict or self.is_ephemeral:
            return (self, None)

        assert self.variant_slice is not None, \
            "variant_slice should always exist for non-conflicted non-ephemeral requests"

        new_slice, package_request = self.variant_slice.extract()
        if not package_request:
            return (self, None)

        assert new_slice is not self.variant_slice
        scope = copy.copy(self)
        scope.variant_slice = new_slice
        if self.pr:
            self.pr("extracted %s from %s", package_request, self)
        return (scope, package_request)

    def split(self) -> tuple[_PackageScope, _PackageScope] | None:
        """Split the scope.

        Returns:
            A (_PackageScope, _PackageScope) tuple, where the first scope is
            guaranteed to have a common dependency. Or None, if splitting is
            not applicable to this scope.
        """
        if (
            self.is_conflict
            or self.is_ephemeral
        ):
            return None

        assert self.variant_slice is not None, \
            "variant_slice should always exist for non-conflicted non-ephemeral requests"

        if len(self.variant_slice) == 1:
            return None

        r = self.variant_slice.split()
        if r is None:
            return None

        slice_, next_slice = r
        scope = self._copy(slice_)
        next_scope = self._copy(next_slice)
        return (scope, next_scope)

    def _copy(self, new_slice: _PackageVariantSlice) -> _PackageScope:
        scope = copy.copy(self)
        scope.variant_slice = new_slice
        scope._update()
        return scope

    def _is_solved(self) -> bool:
        return (
            self.is_conflict
            or self.is_ephemeral
            or (
                self.variant_slice is not None  # should never be None here
                and len(self.variant_slice) == 1
                and not self.variant_slice.extractable
            )
        )

    def _get_solved_variant(self) -> PackageVariant | None:
        if (
            self.variant_slice is not None
            and len(self.variant_slice) == 1
            and not self.variant_slice.extractable
        ):
            return self.variant_slice.first_variant
        else:
            return None

    def _get_solved_ephemeral(self) -> Requirement | None:
        if self.is_ephemeral and not self.is_conflict:
            return self.package_request
        else:
            return None

    def _update(self) -> None:
        if self.variant_slice is not None:
            self.package_request = Requirement.construct(
                self.package_name, self.variant_slice.range_)

    def __str__(self) -> str:
        if self.variant_slice is None:
            return str(self.package_request)
        else:
            return str(self.variant_slice)


def _get_dependency_order(g: digraph, node_list: list[T]) -> list[T]:
    """Return list of nodes as close as possible to the ordering in node_list,
    but with child nodes earlier in the list than parents."""
    access_ = accessibility(g)
    deps = dict((k, set(v) - set([k])) for k, v in access_.items())
    nodes = node_list + sorted(set(g.nodes()) - set(node_list))
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
    def __init__(self, solver: Solver):
        self.solver = solver
        self.failure_reason: FailureReason | None = None
        self.extractions: dict[tuple[str, str], Requirement] = {}
        self.status = SolverStatus.pending

        self.scopes = []
        for package_request in self.solver.request_list:
            scope = _PackageScope(package_request, solver=solver)
            self.scopes.append(scope)

        # only so an initial reduction across all scopes happens in a new phase
        self.changed_scopes_i = set(range(len(self.scopes)))

    @property
    def pr(self) -> _Printer:
        return self.solver.pr

    def solve(self) -> _ResolvePhase:
        """Attempt to solve the phase."""
        if self.status != SolverStatus.pending:
            return self

        scopes = self.scopes[:]
        failure_reason: FailureReason | None = None
        extractions: dict[tuple[str, str], Requirement] = {}

        changed_scopes_i = self.changed_scopes_i.copy()

        def _create_phase(status: SolverStatus | None = None) -> _ResolvePhase:
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
                extracted_requests_ = []

                # perform all possible extractions
                with self.solver.timed(self.solver.extraction_time):
                    for i in range(len(scopes)):
                        while True:
                            scope_, extracted_request = scopes[i].extract()

                            if extracted_request:
                                extracted_requests_.append(extracted_request)
                                k = (scopes[i].package_name, extracted_request.name)
                                extractions[k] = extracted_request
                                self.solver.extractions_count += 1
                                scopes[i] = scope_
                            else:
                                break

                if not extracted_requests_:
                    break

                # simplify extractions (there may be overlaps)
                self.pr.subheader("MERGE-EXTRACTIONS:")
                extracted_requests = RequirementList(extracted_requests_)

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
                        new_scope = scope.intersect(extracted_req.range)

                        req_fams.append(extracted_req.name)

                        if new_scope is None:
                            # the scope conflicted with the extraction
                            conflict = DependencyConflict(
                                extracted_req, scope.package_request)
                            failure_reason = DependencyConflicts([conflict])
                            return _create_phase(SolverStatus.failed)

                        if new_scope is not scope:
                            # the scope was narrowed because it intersected
                            # with an extraction
                            scopes[i] = new_scope
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

                    for req in new_extracted_reqs:
                        try:
                            scope = _PackageScope(req, solver=self.solver)
                        except PackageFamilyNotFoundError as e:
                            # Look up which are requesting the missing one
                            requesters = []
                            for k, extracted_request in extractions.items():
                                if extracted_request.name == req.name:
                                    requesters.append(k[0])
                            if not requesters:
                                # Must have a match. Raise origin error if not
                                raise e
                            else:
                                # Raise with more info when match found
                                searched = "; ".join(self.solver.package_paths)
                                requested = ", ".join(requesters)

                                fail_message = ("package family not found: {}, was required by: {} (searched: {})"
                                                .format(req.name, requested, searched))
                                # TODO: Test with memcached to see if this can cause any conflicting behaviour
                                #       where a package may show as missing/available inadvertently
                                if not config.error_on_missing_variant_requires:
                                    print(fail_message, file=sys.stderr)
                                    return _create_phase(SolverStatus.failed)
                                raise PackageFamilyNotFoundError(
                                    fail_message)

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

            # Create set of pending reductions from the list of changed scopes
            # and list of added scopes. Each item is an (x, y) tuple, where
            # scope[x] will reduce by scope[y].package_request.
            #
            all_scopes_i = range(num_scopes)
            prev_scopes_i = range(prev_num_scopes)
            added_scopes_i = range(prev_num_scopes, num_scopes)

            pending_reducts = set(chain(

                # existing scopes must reduce against changed scopes
                product(prev_scopes_i, changed_scopes_i),

                # existing scopes must reduce against newly added scopes
                product(prev_scopes_i, added_scopes_i),

                # newly added scopes must reduce against all other scopes
                product(added_scopes_i, all_scopes_i),

                # 'widened' scopes (see earlier comment in this func) must reduce
                # against all other scopes
                #
                product(widened_scopes_i, all_scopes_i)
            ))

            # iteratively reduce until there are no more pending reductions.
            # Note that if a scope is reduced, then other scopes need to reduce
            # against it once again.
            #
            with self.solver.timed(self.solver.reduction_test_time):

                # A different order here wouldn't cause an invalid solve, however
                # rez solves must be deterministic, so this is why we sort.
                #
                pending_reducts_ = sorted(pending_reducts)

                while pending_reducts_:
                    x, y = pending_reducts_.pop()
                    if x == y:
                        continue

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
                                pending_reducts_.append((j, x))

            changed_scopes_i = set()

        return _create_phase()

    def finalise(self) -> _ResolvePhase:
        """Remove conflict requests, detect cyclic dependencies, and reorder
        packages wrt dependency and then request order.

        Returns:
            A new copy of the phase with conflict requests removed and packages
            correctly ordered; or, if cyclic dependencies were detected, a new
            phase marked as cyclic.
        """
        assert self._is_solved()
        g = self._get_minimal_graph()
        assert g is not None, "graph should always be present when solved"

        scopes = dict((x.package_name, x) for x in self.scopes
                      if not x.is_conflict)

        # check for cyclic dependencies
        fam_cycle = find_cycle(g)
        if fam_cycle:
            cycle = []
            for fam in fam_cycle:
                scope = scopes[fam]
                variant = scope._get_solved_variant()
                assert variant is not None, "variant should not be None when scope is solved"
                stmt = VersionedObject.construct(fam, variant.version)
                cycle.append(stmt)

            phase = copy.copy(self)
            phase.scopes = list(scopes.values())
            phase.failure_reason = Cycle(cycle)
            phase.status = SolverStatus.cyclic
            return phase

        # reorder wrt dependencies, keeping original request order where possible
        fams = [x.name for x in self.solver.request_list]
        ordered_fams = _get_dependency_order(g, fams)

        scopes_ = []
        for fam in ordered_fams:
            scope = scopes[fam]
            if not scope.is_conflict:
                scopes_.append(scope)

        phase = copy.copy(self)
        phase.scopes = scopes_
        return phase

    def split(self) -> tuple[_ResolvePhase, _ResolvePhase]:
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
        assert self.status == SolverStatus.exhausted

        scopes = []
        next_scopes = []
        split_i: int | None = None

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
        # for i in range(len(phase.scopes)):
        #     if i != split_i:
        #         phase.pending_reducts.add((i, split_i))

        next_phase = copy.copy(phase)
        next_phase.scopes = next_scopes
        return (phase, next_phase)

    def get_graph(self) -> digraph:
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
        scope_requests = {}  # (node_id, request)

        # -- graph creation basics

        node_color = "#F6F6F6"
        request_color = "#FFFFAA"
        solved_color = "#AAFFAA"
        node_fontsize = 10
        counter = [1]

        def _uid() -> str:
            id_ = counter[0]
            counter[0] += 1
            return "_%d" % id_

        def _add_edge(id1: str, id2: str, arrowsize=0.5) -> tuple[str, str]:
            e = (id1, id2)
            if g.has_edge(e):
                g.del_edge(e)
            g.add_edge(e)
            g.add_edge_attribute(e, ("arrowsize", str(arrowsize)))
            return e

        def _add_extraction_merge_edge(id1: str, id2: str):
            e = _add_edge(id1, id2, 1)
            g.add_edge_attribute(e, ("arrowhead", "odot"))

        def _add_conflict_edge(id1: str, id2: str):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, "CONFLICT")
            g.add_edge_attribute(e, ("style", "bold"))
            g.add_edge_attribute(e, ("color", "red"))
            g.add_edge_attribute(e, ("fontcolor", "red"))

        def _add_cycle_edge(id1: str, id2: str):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, "CYCLE")
            g.add_edge_attribute(e, ("style", "bold"))
            g.add_edge_attribute(e, ("color", "red"))
            g.add_edge_attribute(e, ("fontcolor", "red"))

        def _add_reduct_edge(id1: str, id2: str, label: str):
            e = _add_edge(id1, id2, 1)
            g.set_edge_label(e, label)
            g.add_edge_attribute(e, ("fontsize", node_fontsize))

        def _add_node(label: str, color: str, style: str) -> str:
            attrs = [("label", label),
                     ("fontsize", node_fontsize),
                     ("fillcolor", color),
                     ("style", '"%s"' % style)]
            id_ = _uid()
            g.add_node(id_, attrs=attrs)
            return id_

        def _add_request_node(request: Requirement, initial_request: bool = False) -> str:
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

        def _add_scope_node(scope: _PackageScope) -> str:
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
            scope_requests[id_] = scope.package_request
            return id_

        def _add_reduct_node(request: Requirement) -> str:
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
                    assert merged_request is not None
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
                    conflicting_request = conflict.conflicting_request
                    scope_n = scope_nodes.get(conflicting_request.name)
                    scope_r = scope_requests.get(scope_n) if scope_n is not None else None

                    if scope_n is not None \
                            and scope_r is not None \
                            and scope_r.conflicts_with(conflicting_request):
                        # confirmed that scope node is in conflict
                        id1 = _add_request_node(conflicting_request)
                        id2 = scope_n
                    elif scope_n is not None and scope_r is None:
                        # occurs when an existing conflict request conflicts
                        # with a pkg requirement
                        id1 = scope_n
                        id2 = _add_request_node(conflict.dependency)
                    else:
                        id1 = _add_request_node(conflict.dependency)
                        id2 = scope_n or _add_request_node(conflicting_request)

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
                    scope = scopes[request.name]
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

    def _get_minimal_graph(self) -> digraph | None:
        if not self._is_solved():
            return None

        nodes = set()
        edges = set()
        scopes = dict((x.package_name, x) for x in self.scopes)

        for scope in scopes.values():
            if scope.is_conflict:
                continue

            nodes.add(scope.package_name)

            variant = scope._get_solved_variant()
            if variant:
                for req in variant.requires_list.requirements:
                    if not req.conflict:
                        edges.add((scope.package_name, req.name))

        g = digraph()
        g.add_nodes(nodes)
        for e in edges:
            g.add_edge(e)

        return g

    def _is_solved(self) -> bool:
        for scope in self.scopes:
            if not scope._is_solved():
                return False
        return True

    def _get_solved_variants(self) -> list[PackageVariant]:
        variants = []
        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                variants.append(variant)

        return variants

    def _get_solved_ephemerals(self) -> list[Requirement]:
        ephemerals = []
        for scope in self.scopes:
            ephemeral = scope._get_solved_ephemeral()
            if ephemeral:
                ephemerals.append(ephemeral)

        return ephemerals

    def __str__(self) -> str:
        return ' '.join(str(x) for x in self.scopes)


class Solver(_Common):
    """Solver.

    A package solver takes a list of package requests (the 'request'), then
    runs a resolve algorithm in order to determine the 'resolve' - the list of
    non-conflicting packages that include all dependencies.
    """
    max_verbosity = 3

    def __init__(self,
                 package_requests: list[Requirement],
                 package_paths: list[str],
                 context: ResolvedContext | None = None,
                 package_filter: PackageFilterBase | None = None,
                 package_orderers: list[PackageOrder] | None = None,
                 callback: Callable[[SolverState], tuple[SolverCallbackReturn, str]] | None = None,
                 building: bool = False,
                 optimised: bool = True,
                 verbosity: int = 0,
                 buf: SupportsWrite | None = None,
                 package_load_callback: Callable[[Package], Any] | None = None,
                 prune_unfailed: bool = True,
                 suppress_passive: bool = False,
                 print_stats: bool = False):
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
        self.context = context

        self.pr = _Printer(verbosity, buf=buf, suppress_passive=suppress_passive)
        self.print_stats = print_stats
        self.buf = buf

        if _force_unoptimised_solver:
            self.optimised = False
        else:
            self.optimised = optimised

        # these values are all set in _init()
        self.phase_stack: list[_ResolvePhase]
        self.failed_phase_list: list[_ResolvePhase]
        self.depth_counts: dict
        self.solve_begun: bool
        self.solve_time: float
        self.load_time: float

        self.abort_reason: str | None = None
        self.callback_return: SolverCallbackReturn | None = None

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
    def timed(self, target: list[float]) -> Generator:
        t = time.time()
        yield
        secs = time.time() - t
        target[0] += secs

    @property
    def status(self) -> SolverStatus:
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
    def num_solves(self) -> int:
        """Return the number of solve steps that have been executed."""
        return self.solve_count

    @property
    def num_fails(self) -> int:
        """Return the number of failed solve steps that have been executed.
        Note that num_solves is inclusive of failures."""
        n = len(self.failed_phase_list)
        if self.phase_stack[-1].status in (SolverStatus.failed, SolverStatus.cyclic):
            n += 1
        return n

    @property
    def cyclic_fail(self) -> bool:
        """Return True if the solve failed due to a cycle, False otherwise."""
        return (self.phase_stack[-1].status == SolverStatus.cyclic)

    @property
    def resolved_packages(self) -> list[PackageVariant] | None:
        """Return a list of resolved variants.

        Returns:
            list of `PackageVariant`: Resolved variants, or None if the resolve
            did not complete or was unsuccessful.
        """
        if (self.status != SolverStatus.solved):
            return None

        final_phase = self.phase_stack[-1]
        return final_phase._get_solved_variants()

    @property
    def resolved_ephemerals(self) -> list[Requirement] | None:
        """Return the list of final ephemeral package ranges.

        Note that conflict ephemerals are not included.

        Returns:
            List of `Requirement`: Final non-conflict ephemerals, or None
            if the resolve did not complete or was unsuccessful.
        """
        if (self.status != SolverStatus.solved):
            return None

        final_phase = self.phase_stack[-1]
        return final_phase._get_solved_ephemerals()

    def reset(self) -> None:
        """Reset the solver, removing any current solve."""
        if not self.request_list.conflict:
            phase = _ResolvePhase(solver=self)
            self.pr("resetting...")
            self._init()
            self._push_phase(phase)

    def solve(self) -> None:
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
    def solve_stats(self) -> dict[str, dict[str, Any]]:
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

    def solve_step(self) -> None:
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
            assert new_phase.status == SolverStatus.exhausted
            self._push_phase(new_phase)

    def failure_reason(self, failure_index: int | None = None) -> FailureReason | None:
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

    def failure_description(self, failure_index: int | None = None) -> str:
        """Get a description of the failure.

        This differs from `failure_reason` - in some cases, such as when a
        callback forces a failure, there is more information in the description
        than there is from `failure_reason`.
        """
        _, description = self._get_failed_phase(failure_index)
        return description

    def failure_packages(self, failure_index: int | None = None) -> list[Requirement] | None:
        """Get packages involved in a failure.

        Args:
            failure_index: See `failure_reason`.

        Returns:
            A list of Requirement objects.
        """
        phase, _ = self._get_failed_phase(failure_index)
        fr = phase.failure_reason
        return fr.involved_requirements() if fr else None

    def get_graph(self) -> digraph:
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
            assert phase is not None, "Should only be None if status is failed"
            return phase.get_graph()
        else:
            return self.get_fail_graph()

    def get_fail_graph(self, failure_index: int | None = None) -> digraph:
        """Returns a graph showing a solve failure.

        Args:
            failure_index: See `failure_reason`

        Returns:
            A pygraph.digraph object.
        """
        phase, _ = self._get_failed_phase(failure_index)
        return phase.get_graph()

    def dump(self) -> None:
        """Print a formatted summary of the current solve state."""
        from rez.utils.formatting import columnise

        rows = []
        for i, phase in enumerate(self.phase_stack):
            rows.append((self._depth_label(i), phase.status, str(phase)))

        print("status: %s (%s)" % (self.status.name, self.status.value[0]))
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

    def _init(self) -> None:
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

    def _latest_nonfailed_phase(self) -> _ResolvePhase | None:
        if self.status == SolverStatus.failed:
            return None

        for phase in reversed(self.phase_stack):
            if phase.status not in (SolverStatus.failed, SolverStatus.cyclic):
                return phase
        assert False  # should never get here

    def _do_callback(self) -> bool:
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

    def _get_variant_slice(self, package_name: str, range_: VersionRange) -> _PackageVariantSlice | None:
        slice_ = self.package_cache.get_variant_slice(
            package_name=package_name, range_=range_)

        return slice_

    def _push_phase(self, phase: _ResolvePhase) -> None:
        depth = len(self.phase_stack)
        count = self.depth_counts.get(depth, -1) + 1
        self.depth_counts[depth] = count
        self.phase_stack.append(phase)

        if self.pr:
            dlabel = self._depth_label()
            self.pr("pushed %s: %s", dlabel, phase)

    def _pop_phase(self) -> _ResolvePhase:
        dlabel = self._depth_label()
        phase = self.phase_stack.pop()
        if self.pr:
            self.pr("popped %s: %s", dlabel, phase)
        return phase

    def _get_failed_phase(self, index: int | None = None) -> tuple[_ResolvePhase, str]:
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

        if phase.failure_reason is None:
            fail_description = "Solver failed with unknown reason."
        else:
            fail_description = phase.failure_reason.description()
        if prepend_abort_reason and self.abort_reason:
            fail_description = "%s:\n%s" % (self.abort_reason, fail_description)

        return phase, fail_description

    def _depth_label(self, depth: int | None = None) -> str:
        if depth is None:
            depth = len(self.phase_stack) - 1
        count = self.depth_counts[depth]
        return "{%d,%d}" % (depth, count)

    def __str__(self) -> str:
        return "%s %s %s" % (self.status,
                             self._depth_label(),
                             str(self.phase_stack[-1]))


def _short_req_str(package_request: Requirement) -> str:
    """print shortened version of '==X|==Y|==Z' ranged requests."""
    if not package_request.conflict:
        versions = package_request.range.to_versions()
        if versions and len(versions) == len(package_request.range) \
                and len(versions) > 1:
            return "%s-%s(%d)" % (package_request.name,
                                  str(package_request.range.span()),
                                  len(versions))
    return str(package_request)
