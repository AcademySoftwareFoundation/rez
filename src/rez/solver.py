"""
The dependency resolving module.

This gives direct access to the solver. You should use the resolve() function
in resolve.py instead, which will use cached data where possible to provide you
with a faster resolve.


A 'phase' is a current state of the solve. It contains a list of 'scopes'.

A 'scope' is a package request. If the request isn't a conflict, then a scope
also contains the actual list of variants that match the request.

The solve loop performs 5 different types of operations:

* EXTRACTION. This happens when a common dependency is found in all the variants
  in a scope. For example if every version of pkg 'foo' depends on some version
  of python, the 'extracted' dependency might be "python-2.6|2.7". An extraction
  then results in either an INTERSECT or an ADD.

* INTERSECT: This happens when an extracted dependency overlaps with an existing
  scope. For example "python-2" might be a current scope. Pkg foo's common dependency
  python-2.6|2.7 would be 'intersected' with this scope. This might result in a
  conflict, which would cause the whole phase to fail (and possibly the whole solve).
  Or, as in this case, it narrows an existing scope to 'python-2.6|2.7'.

* ADD: This happens when an extraction is a new pkg request. A new scope is
  created and added to the current list of scopes.

* REDUCE: This is when a scope iterates over all of its variants and removes those
  that conflict with another scope. If this removes all the variants in the scope,
  the phase has failed - this is called a "total reduction". This type of failure
  is not common - usually it's a conflicting INTERSECT that causes a failure.

* SPLIT: Once a phase has been extracted/intersected/added/reduced as much as
  possible (this is called 'exhausted'), we are left with either a solution (each
  scope contains only a single variant), or an unsolved phase. This is when the
  algorithm needs to recurse (although it doesn't actually recurse, it uses a stack
  instead). A SPLIT occurs at this point. The first scope with more than one
  variant is found. This scope is split in two (let us say ScopeA and ScopeB),
  where ScopeA has at least one common dependency (worst case scenario, ScopeA
  contains a single variant). This is done because it guarantees a later extraction,
  which hopefully gets us closer to a solution. Now, two phases are created (let us
  say PhaseA and PhaseB) - identical to the current phase, except that PhaseA has
  ScopeA instead of the original, and PhaseB has ScopeB instead of the original.
  Now, we attempt to solve PhaseA, and if that fails, we attempt to solve PhaseB.

The pseudocode for a solve looks like this::

    def solve(requests):
        phase = create_initial_phase(requests)
        phase_stack = stack()
        phase_stack.push(phase)

        while not solved():
            phase = phase_stack.pop()
            if phase.failed:
                phase = phase_stack.pop()  # discard previous failed phase

            if phase.exhausted:
                phase, next_phase = phase.split()
                phase_stack.push(next_phase)

            new_phase = solve_phase(phase)
            if new_phase.failed:
                phase_stack.push(new_phase)  # we keep last fail on the stack
            elif new_phase.solved:
                # some housekeeping here, like checking for cycles
                final_phase = finalise_phase(new_phase)
                phase_stack.push(final_phase)
            else:
                phase_stack.push(new_phase)  # phase is exhausted

    def solve_phase(phase):
        while True:
            while True:
                foreach phase.scope as x:
                    extractions |= collect_extractions(x)

                if extractions_present:
                    foreach phase.scope as x:
                        intersect(x, extractions)
                        if failed(x):
                            set_fail()
                            return
                        elif intersected(x):
                            reductions |= add_reductions_involving(x)

                    foreach new_request in extractions:
                        scope = new_scope(new_request)
                        reductions |= add_reductions_involving(scope)
                        phase.add(scope)
                else:
                    break

            if no intersections and no adds:
                break

            foreach scope_a, scope_b in reductions:
                scope_b.reduce_by(scope_a)
                if totally_reduced(scope_b):
                    set_fail()
                    return

There are 2 notable points missing from the pseudocode, related to optimisations:

* Scopes keep a set of package families so that they can quickly skip unnecessary
  reductions. For example, all 'foo' pkgs may depend only on the set (python, bah),
  so when reduced against 'maya', this becomes basically a no-op.

* Objects in the solver (phases, scopes etc) are immutable. Whenever a change
  occurs - such as a scope being narrowed as a result of an intersect - what
  actually happens is that a new object is created, often based on a shallow copy
  of the previous object. This is basically implementing copy-on-demand - lots of
  scopes are shared between phases in the stack, if objects were not immutable
  then creating a new phase would involve a deep copy of the entire state of the
  solver.
"""
from rez.config import config
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.algorithms.cycles import find_cycle
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PackageFamilyNotFoundError
from rez.vendor.version.version import Version, VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement, \
    RequirementList
from rez.vendor.enum import Enum
from rez.packages_ import iter_packages
from itertools import groupby
import copy
import time
import sys


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
    def __init__(self, verbosity, buf=None):
        self.verbosity = verbosity
        self.buf = buf or sys.stdout
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

    def important(self, txt, *args):
        if self.verbosity > 1:
            self.pr(txt % args)

    def br(self):
        self.pending_br = True

    def pr(self, txt='', *args):
        print >> self.buf, txt % args

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
        range = VersionRange.from_version(self.version)
        req = Requirement.construct(self.name, range)
        return [req, self.dependency, self.conflicting_request]

    def __eq__(self, other):
        return (self.name == other.name and
                self.version == other.version and
                self.variant_index == other.variant_index and
                self.dependency == other.dependency and
                self.conflicting_request == other.conflicting_request)

    def __str__(self):
        return "%s --> %s <--!--> %s)" \
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
    """A variant of a package."""
    def __init__(self, name, version, requires, index=None, userdata=None):
        """Create a package variant.

        Args:
            name: Name of package.
            version: The package version, as a Version object.
            requires: List of strings representing the package dependencies.
            index: Zero-based index of the variant within this package. If
                None, this package does not have variants.
            userdata: Arbitrary extra data to attach to the variant.
        """
        self.name = name
        self.version = version
        self.index = index
        self.userdata = userdata
        self.requires_list = RequirementList(requires)

        if self.requires_list.conflict:
            raise ResolveError(("The package %s has an internal "
                               "requirements conflict: %s")
                               % (str(self), str(self.requires_list)))

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


class _PackageVariantList(_Common):
    """A list of package variants, loaded lazily.

    Variants are sorted by descending version. However sorting within a version
    is not done here - that only happens on a split().
    """
    def __init__(self, package_name, package_paths=None, timestamp=0,
                 building=False, package_load_callback=None):
        self.package_name = package_name
        self.package_paths = package_paths
        self.timestamp = timestamp
        self.building = building
        self.package_load_callback = package_load_callback
        self.variants = []

        it = iter_packages(self.package_name, paths=self.package_paths)
        entries = ([x.version, x] for x in it)
        self.entries = sorted(entries, key=lambda x: x[0], reverse=True)
        if not self.entries:
            raise PackageFamilyNotFoundError(
                "package family not found: %s (searched: %s)"
                % (package_name, "; ".join(self.package_paths)))

    def get_intersection(self, range):
        """Get a list of variants that intersect with the given range.

        Args:
            range (`VersionRange`): Package version range.

        Returns:
            List of `PackageVariant` objects, in descending version order.
        """
        variants = []

        for entry in self.entries:
            version, value = entry
            if version not in range:
                continue

            if isinstance(value, list):
                variants.extend(value)
            else:
                # expand package entry into list of variants
                package = value
                if self.package_load_callback:
                    self.package_load_callback(package)

                if self.timestamp and package.timestamp > self.timestamp:
                    continue  # access to timestamp causes a package load

                variants_ = []
                for var in package.iter_variants():
                    requires = var.get_requires(build_requires=self.building)
                    userdata = var.handle.to_dict()
                    variant = PackageVariant(name=self.package_name,
                                             version=var.version,
                                             requires=requires,
                                             index=var.index,
                                             userdata=userdata)
                    variants_.append(variant)
                entry[1] = variants_
                variants.extend(variants_)

        return variants or None

    def dump(self):
        print self.package_name
        for version, variants in self.entries:
            print str(version)
            for variant in variants:
                print "    %s" % str(variant)

    def __str__(self):
        strs = []
        for _, variants in self.entries:
            strs.append(','.join(str(x) for x in variants))
        return "%s[%s]" % (self.package_name, ' '.join(strs))


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


class _PackageVariantSlice(_Common):
    """A subset of a variant list, but with more dependency-related info."""
    def __init__(self, package_name, variants, printer=None):
        self.package_name = package_name
        self.variants = variants
        self.pr = printer
        self.range = None

        # family tracking
        self.extracted_fams = set()
        self.fam_requires = None
        self.common_fams = None

        self._update()

    @property
    def extractable(self):
        """True if there are possible remaining extractions."""
        return not self.extracted_fams.issuperset(self.common_fams)

    def intersect(self, range):
        """Remove variants whos version fall outside of the given range."""
        if self.pr:
            self.pr("intersecting %s wrt range '%s'...", self, range)

        if range.is_any():
            return self

        variants = []
        it = groupby(self.variants, lambda x: x.version)
        it2 = range.contains_versions(it, key=lambda x: x[0], descending=True)
        for contains, (_, variants_) in it2:
            if contains:
                variants.extend(variants_)

        if not variants:
            return None
        elif len(variants) < len(self.variants):
            return self._copy(variants)
        else:
            return self

    def reduce_by(self, package_request):
        """Remove variants whos dependencies conflict with the given package
        request.

        Returns:
            (VariantSlice, [Reduction]) tuple, where slice may be None if all
            variants were reduced.
        """
        if (package_request.range is None) or \
                (package_request.name not in self.fam_requires):
            return (self, [])

        if self.pr:
            reqstr = _short_req_str(package_request)
            self.pr("reducing %s wrt %s...", self, reqstr)

        variants = []
        reductions = []
        fn = lambda x: x.get(package_request.name)

        for req, variants_ in groupby(self.variants, fn):
            if req and req.conflicts_with(package_request):
                for variant in variants_:
                    red = Reduction(name=variant.name,
                                    version=variant.version,
                                    variant_index=variant.index,
                                    dependency=req,
                                    conflicting_request=package_request)
                    reductions.append(red)
                    if self.pr:
                        self.pr("removed %s (dep(%s) <--!--> %s)",
                                red.reducee_str(),
                                red.dependency,
                                red.conflicting_request)
            else:
                variants.extend(variants_)

        if not variants:
            return (None, reductions)
        elif reductions:
            return (self._copy(variants), reductions)
        else:
            return (self, [])

    def extract(self):
        """Extract a common dependency.

        Note that conflict dependencies are never extracted, they are always
        resolved via reduction.
        """
        if self.extractable:
            extractable = self.common_fams - self.extracted_fams
            fam = iter(extractable).next()
            ranges = []

            for variant in self.variants:
                req = variant.get(fam)
                if not ranges or req.range != ranges[-1]:
                    ranges.append(req.range)

            slice_ = copy.copy(self)
            slice_.extracted_fams = self.extracted_fams | set([fam])

            range_ = ranges[0].union(ranges[1:])
            common_req = Requirement.construct(fam, range_)
            return (slice_, common_req)
        else:
            return (self, None)

    def split(self, package_requests):
        """Split the slice."""
        if len(self.variants) == 1:
            return None

        self.sort_variants(package_requests)
        it = enumerate(self.variants)
        latest_variant = it.next()[1]
        split_fams = None
        nleading = 1

        if len(self.variants) > 2:
            fams = latest_variant.request_fams - self.extracted_fams
            if fams:
                for j, variant in it:
                    next_fams = variant.request_fams & fams
                    if next_fams:
                        fams = next_fams
                    else:
                        split_fams = fams
                        nleading = j
                        break

        slice_ = self._copy(self.variants[:nleading])
        next_slice = self._copy(self.variants[nleading:])

        if self.pr:
            s = "split %s into %s and %s"
            a = [self, slice_, next_slice]
            if split_fams is None:
                s += " on leading variant"
            else:
                s += " on %d leading variants with common dependencies: %s"
                a.extend([nleading, ", ".join(split_fams)])
            self.pr(s, *a)

        return (slice_, next_slice)

    def sort_variants(self, package_requests):
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
        - THEN highest versions of packages shared with request;
        - THEN least number of additional packages added to solve;
        - THEN highest versions of additional packages;
        - THEN alphabetical on name of additional packages;
        - THEN variant index.

        Note:
            In theory 'variant.index' should never factor into the sort unless
            two variants are identical (which shouldn't happen) - this is jusst
            here as a safety measure so that sorting is guaranteed repeatable
            regardless.

        Note:
            Assumes self.variants is already in version-descending order.
        """
        def key(variant):
            k1 = []
            names = set()
            for i, request in enumerate(package_requests):
                if not request.conflict:
                    req = variant.requires_list.get(request.name)
                    if req is not None:
                        k1.append((-i, req.range))
                        names.add(req.name)

            k2 = []
            for request in variant.requires_list:
                if not request.conflict and request.name not in names:
                    k2.append((request.range, request.name))

            if config.variant_select_mode == VariantSelectMode.version_priority:
                k = (k1, -len(k2), k2, variant.index)
            else:  # VariantSelectMode.intersection_priority
                k = (len(k1), k1, -len(k2), k2, variant.index)

            return k

        variants2 = []
        for _, it in groupby(self.variants, lambda x: x.version):
            variants3 = list(it)
            if len(variants3) == 1:
                variants2.extend(variants3)
            else:
                variants4 = sorted(variants3, key=key, reverse=True)
                variants2.extend(variants4)

        self.variants = variants2

    def dump(self):
        print self.package_name
        print '\n'.join(map(str, self.variants))

    def _copy(self, new_variants):
        slice_ = copy.copy(self)
        slice_.variants = new_variants
        slice_.extracted_fams = set()
        slice_._update()
        return slice_

    def _update(self):
        # range
        versions = set(x.version for x in self.variants)
        self.range = VersionRange.from_versions(versions)

        # family-related
        self.common_fams = set(self.variants[0].request_fams)
        self.fam_requires = set()

        for variant in self.variants:
            self.common_fams &= variant.request_fams
            self.fam_requires |= (variant.request_fams |
                                  variant.conflict_request_fams)

    def __len__(self):
        return len(self.variants)

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
        nvariants = len(self.variants)
        if nvariants == 1:
            variant = self.variants[0]
            s_idx = "" if variant.index is None else "[%d]" % variant.index
            s = "[%s==%s%s]" % (self.package_name, str(variant.version), s_idx)
        else:
            nversions = len(set(x.version for x in self.variants))
            if nversions == 1:
                indexes = sorted([x.index for x in self.variants])
                s_idx = ','.join(str(x) for x in indexes)
                verstr = str(self.variants[0].version)
                s = "[%s==%s[%s]]" % (self.package_name, verstr, s_idx)
            else:
                verstr = "%d" % nvariants if (nversions == nvariants) \
                    else "%d:%d" % (nversions, nvariants)

                span = self.range.span()
                s = "%s[%s(%s)]" % (self.package_name, str(span), verstr)

        strextr = '*' if self.extractable else ''
        return s + strextr


class PackageVariantCache(object):
    def __init__(self, package_paths, timestamp=0, building=False,
                 package_load_callback=None):
        self.package_paths = package_paths
        self.timestamp = timestamp
        self.building = building
        self.package_load_callback = package_load_callback
        self.variant_lists = {}  # {package-name: _PackageVariantList}

    def get_variant_slice(self, package_name, range):
        """Get a list of variants from the cache.

        Args:
            package_name (str): Name of package.
            range (`VersionRange`): Package version range.

        Returns:
            `_PackageVariantSlice` object.
        """
        variant_list = self.variant_lists.get(package_name)
        if variant_list is None:
            variant_list = _PackageVariantList(
                package_name,
                package_paths=self.package_paths,
                timestamp=self.timestamp,
                building=self.building,
                package_load_callback=self.package_load_callback)
            self.variant_lists[package_name] = variant_list

        variants = variant_list.get_intersection(range)
        if not variants:
            return None, False

        slice_ = _PackageVariantSlice(package_name, variants=variants)
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

    def intersect(self, range):
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
                    self.package_name, range)
            else:
                new_range = range - self.package_request.range
                if new_range is not None:
                    new_slice = self.solver._get_variant_slice(
                        self.package_name, new_range)
        else:
            new_slice = self.variant_slice.intersect(range)

        if new_slice is None:
            if self.pr:
                self.pr("%s intersected with range '%s' resulted in no packages",
                        self, range)
            return None
        elif new_slice is not self.variant_slice:
            scope = self._copy(new_slice)
            if self.pr:
                self.pr("%s was intersected to %s by range '%s'",
                        self, scope, range)
            return scope
        else:
            return self

    def reduce_by(self, package_request):
        """Reduce this scope wrt a package request.

        Returns:
            A (_PackageScope, [Reduction]) tuple, where the scope is a new
            scope copy with reductions applied, or self if there were no
            reductions, or None if the slice was completely reduced.
        """
        if not self.package_request.conflict:
            new_slice, reductions = self.variant_slice.reduce_by(package_request)

            if new_slice is None:
                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr("%s was reduced to nothing by %s", self, reqstr)
                    self.pr.br()
                return (None, reductions)
            elif new_slice is not self.variant_slice:
                scope = self._copy(new_slice)

                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr("%s was reduced to %s by %s", self, scope, reqstr)
                    self.pr.br()
                return (scope, reductions)

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

    def split(self, package_requests):
        """Split the scope.

        Returns:
            A (_PackageScope, _PackageScope) tuple, where the first scope is
            guaranteed to have a common dependency. Or None, if splitting is
            not applicable to this scope.
        """
        if self.package_request.conflict or (len(self.variant_slice) == 1):
            return None
        else:
            r = self.variant_slice.split(package_requests)
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
            return self.variant_slice.variants[0]
        else:
            return None

    def _update(self):
        if self.variant_slice is not None:
            self.package_request = Requirement.construct(
                self.package_name, self.variant_slice.range)

    def __str__(self):
        return str(self.variant_slice) if self.variant_slice \
            else str(self.package_request)


def _get_dependency_order(g, node_list):
    """Return list of nodes as close as possible to the ordering in node_list,
    but with child nodes earlier in the list than parents."""
    access_ = accessibility(g)
    deps = dict((k, set(v) - set([k])) for k, v in access_.iteritems())
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
    def __init__(self, package_requests, solver):
        self.package_requests = package_requests
        self.failure_reason = None
        self.extractions = {}
        self.solver = solver
        self.pr = solver.pr
        self.status = SolverStatus.pending

        self.scopes = []
        for package_request in package_requests:
            scope = _PackageScope(package_request, solver=solver)
            self.scopes.append(scope)

        self.pending_reducts = set()
        for i in range(len(self.scopes)):
            for j in range(len(self.scopes)):
                if i != j:
                    self.pending_reducts.add((i, j))

    def solve(self):
        """Attempt to solve the phase."""
        if self.status != SolverStatus.pending:
            return self

        scopes = self.scopes[:]
        failure_reason = None
        extractions = {}
        pending_reducts = self.pending_reducts.copy()

        def _create_phase(status=None):
            phase = copy.copy(self)
            phase.scopes = scopes
            phase.failure_reason = failure_reason
            phase.extractions = extractions
            phase.pending_reducts = set()

            if status is None:
                phase.status = (SolverStatus.solved if phase._is_solved()
                                else SolverStatus.exhausted)
            else:
                phase.status = status
            return phase

        while True:
            # iteratively extract until no more extractions possible
            while True:
                self.pr.subheader("EXTRACTING:")
                common_requests = []

                for i in range(len(scopes)):
                    while True:
                        scope_, common_request = scopes[i].extract()
                        if common_request:
                            common_requests.append(common_request)
                            k = (scopes[i].package_name, common_request.name)
                            extractions[k] = common_request
                            scopes[i] = scope_
                        else:
                            break

                if common_requests:
                    request_list = RequirementList(common_requests)
                    if request_list.conflict:
                        # two or more extractions are in conflict
                        req1, req2 = request_list.conflict
                        conflict = DependencyConflict(req1, req2)
                        failure_reason = DependencyConflicts([conflict])
                        return _create_phase(SolverStatus.failed)
                    else:
                        if self.pr:
                            self.pr("merged extractions: %s", request_list)
                        """
                        # flake8 founs this, I don't remember why it's here...
                        if len(request_list.requirements) < len(common_requests):
                            for req in request_list.requirements:
                                src_reqs = [x for x in common_requests
                                            if x.name == req.name]
                        """

                    # do intersections with existing scopes
                    self.pr.subheader("INTERSECTING:")
                    req_fams = []

                    for i, scope in enumerate(scopes):
                        req = request_list.get(scope.package_name)
                        if req is not None:
                            scope_ = scope.intersect(req.range)
                            req_fams.append(req.name)

                            if scope_ is None:
                                conflict = DependencyConflict(
                                    req, scope.package_request)
                                failure_reason = DependencyConflicts([conflict])
                                return _create_phase(SolverStatus.failed)
                            elif scope_ is not scope:
                                scopes[i] = scope_
                                for j in range(len(scopes)):
                                    if j != i:
                                        pending_reducts.add((i, j))

                    # add new scopes
                    self.pr.subheader("ADDING:")
                    new_reqs = [x for x in request_list.requirements
                                if x.name not in req_fams]

                    if new_reqs:
                        n = len(scopes)
                        for req in new_reqs:
                            scope = _PackageScope(req, solver=self.solver)
                            scopes.append(scope)
                            if self.pr:
                                self.pr("added %s", scope)

                        m = len(new_reqs)
                        for i in range(n, n + m):
                            for j in range(n + m):
                                if i != j:
                                    pending_reducts.add((i, j))

                        for i in range(n):
                            for j in range(n, n + m):
                                pending_reducts.add((i, j))
                else:
                    break

            if not pending_reducts:
                break

            # iteratively reduce until no more reductions possible
            self.pr.subheader("REDUCING:")

            if not self.solver.optimised:
                # check all variants for reduction regardless
                pending_reducts = set()
                for i in range(len(scopes)):
                    for j in range(len(scopes)):
                        if i != j:
                            pending_reducts.add((i, j))

            while pending_reducts:
                new_pending_reducts = set()

                # the sort here gives reproducible results, since order of
                # reducts affects the result
                for i, j in sorted(pending_reducts):
                    new_scope, reductions = scopes[j].reduce_by(
                        scopes[i].package_request)
                    if new_scope is None:
                        failure_reason = TotalReduction(reductions)
                        return _create_phase(SolverStatus.failed)
                    elif new_scope is not scopes[j]:
                        scopes[j] = new_scope
                        for i in range(len(scopes)):
                            if i != j:
                                new_pending_reducts.add((j, i))

                pending_reducts = new_pending_reducts

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
        fams = [x.name for x in self.package_requests]
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
        split = None

        for i, scope in enumerate(self.scopes):
            if split is None:
                r = scope.split(self.solver.package_requests)
                if r is not None:
                    scope_, next_scope = r
                    scopes.append(scope_)
                    next_scopes.append(next_scope)
                    split = i
                    continue

            scopes.append(scope)
            next_scopes.append(scope)

        phase = copy.copy(self)
        phase.scopes = scopes
        phase.status = SolverStatus.pending

        for i in range(len(phase.scopes)):
            if i != split:
                phase.pending_reducts.add((split, i))

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
        for request in self.package_requests:
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
        for request in self.package_requests:
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
        for (src_fam, _), dest_req in self.extractions.iteritems():
            id1 = scope_nodes.get(src_fam)
            if id1 is not None:
                id2 = _add_request_node(dest_req)
                _add_edge(id1, id2)

        # add extraction intersections
        extracted_fams = set(x[1] for x in self.extractions.iterkeys())
        for fam in extracted_fams:
            requests = [v for k, v in self.extractions.iteritems() if k[1] == fam]
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
        for request, id1 in request_nodes.iteritems():
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

            for n, access_nodes in access_dict.iteritems():
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

        for scope in scopes.itervalues():
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

    def __init__(self, package_requests, package_paths, timestamp=0,
                 callback=None, building=False, optimised=True, verbosity=0,
                 buf=None, package_load_callback=None, package_cache=None,
                 prune_unfailed=True):
        """Create a Solver.

        Args:
            package_requests: List of Requirement objects representing the
                request.
            package_paths: List of paths to search for pkgs.
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
            package_cache (`PackageVariantCache`): Provided variant cache. The
                `Resolver` may use this to share a single cache across several
                `Solver` instances.
            prune_unfailed (bool): If the solve failed, and `prune_unfailed` is
                True, any packages unrelated to the conflict are removed from
                the graph.
        """
        self.package_requests = package_requests
        self.package_paths = package_paths
        self.pr = _Printer(verbosity, buf=buf)
        self.optimised = optimised
        self.timestamp = timestamp
        self.callback = callback
        self.prune_unfailed = prune_unfailed
        self.request_list = None

        self.phase_stack = None
        self.failed_phase_list = None
        self.abort_reason = None
        self.callback_return = None
        self.solve_count = None
        self.depth_counts = None
        self.solve_time = None
        self.load_time = None
        self.solve_begun = None
        self._init()

        if package_cache:
            self.package_cache = package_cache
        else:
            self.package_cache = PackageVariantCache(
                self.package_paths,
                timestamp=timestamp,
                package_load_callback=package_load_callback,
                building=building)

        # merge the request
        if self.pr:
            self.pr("request: %s", ' '.join(map(str, package_requests)))
        self.request_list = RequirementList(package_requests)

        if self.request_list.conflict:
            req1, req2 = self.request_list.conflict
            if self.pr:
                self.pr("conflict in request: %s <--!--> %s", req1, req2)

            conflict = DependencyConflict(req1, req2)
            phase = _ResolvePhase(package_requests, solver=self)
            phase.failure_reason = DependencyConflicts([conflict])
            phase.status = SolverStatus.failed
            self._push_phase(phase)
            return
        elif self.pr:
            s = ' '.join(map(str, self.request_list.requirements))
            self.pr("merged request: %s", s)

        # create the initial phase
        phase = _ResolvePhase(self.request_list.requirements, solver=self)
        self._push_phase(phase)

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
        self.solve_time = 0.0
        self.load_time = 0.0

        # iteratively solve phases
        while self.status == SolverStatus.unsolved:
            self.solve_step()
            if self.status == SolverStatus.unsolved and not self._do_callback():
                break

    def solve_step(self):
        """Perform a single solve step.
        """
        self.solve_begun = True
        if self.status != SolverStatus.unsolved:
            return

        if self.pr:
            self.pr.header("SOLVE #%d...", self.solve_count + 1)
        start_time = time.time()
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
        self.pr.subheader("RESULT:")

        if new_phase.status == SolverStatus.failed:
            self.pr("phase failed to resolve")
            self._push_phase(new_phase)
            if self.pr and len(self.phase_stack) == 1:
                self.pr.header("FAIL: there is no solution")
        elif new_phase.status == SolverStatus.solved:
            # solved, but there may be cyclic dependencies
            final_phase = new_phase.finalise()
            self._push_phase(final_phase)

            if self.pr:
                if final_phase.status == SolverStatus.cyclic:
                    self.pr.header("FAIL: a cycle was detected")
                else:
                    self.pr.header("SUCCESS")
                    self.pr("solve time: %.2f seconds", self.solve_time)
                    self.pr("load time: %.2f seconds", self.load_time)
        else:
            assert(new_phase.status == SolverStatus.exhausted)
            self._push_phase(new_phase)
            if self.pr:
                s = SolverState(self.num_solves, self.num_fails, new_phase)
                self.pr.important(str(s))

        end_time = time.time()
        self.solve_time += (end_time - start_time)

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

        print "status: %s (%s)" % (self.status.name, self.status.description)
        print "initial request: %s" % str(self.request_list)
        print
        print "solve stack:"
        print '\n'.join(columnise(rows))

        if self.failed_phase_list:
            rows = []
            for i, phase in enumerate(self.failed_phase_list):
                rows.append(("#%d" % i, phase.status, str(phase)))
            print
            print "previous failures:"
            print '\n'.join(columnise(rows))

    def _init(self):
        self.phase_stack = []
        self.failed_phase_list = []
        self.solve_count = 0
        self.depth_counts = {}
        self.solve_time = 0.0
        self.load_time = 0.0
        self.solve_begun = False

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

    def _get_variant_slice(self, package_name, range):
        start_time = time.time()
        slice_ = self.package_cache.get_variant_slice(package_name=package_name,
                                                      range=range)

        if slice_ is not None:
            slice_.pr = self.pr

        end_time = time.time()
        self.load_time += (end_time - start_time)
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
