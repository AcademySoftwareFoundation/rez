"""
The dependency resolving module.

This gives direct access to the solver. You should use the resolve() function
in resolve.py instead, which will use cached data where possible to provide you
with a faster resolve.
"""
from rez.contrib.pygraph.classes.digraph import digraph
from rez.contrib.pygraph.algorithms.cycles import find_cycle
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PkgFamilyNotFoundError
from rez.version import VersionRange
from rez.packages import PackageStatement, PackageRangeStatement, \
    iter_packages_in_range
from rez.util import columnise
from rez.settings import settings
import copy
import time



class _Printer(object):
    def __init__(self, verbose):
        self.verbose = verbose
        self.pending_sub = None
        self.pending_br = False
        self.last_pr = True

    def header(self, txt):
        if self.verbose:
            print
            print '-' * 80
            print txt
            print '-' * 80
            self.pending_br = False
            self.pending_sub = None
            self.last_pr = False

    def subheader(self, txt):
        self.pending_sub = txt

    def __call__(self, txt):
        if self.verbose:
            if self.pending_sub:
                if self.last_pr:
                    print
                print self.pending_sub
                self.pending_sub = None
            elif self.pending_br:
                print

            print txt
            self.last_pr = True
            self.pending_br = False

    def br(self):
        self.pending_br = True

    def __nonzero__(self):
        return self.verbose



class _Common(object):
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))



class PackageRequestList(_Common):
    """A list of package requests.

    This class takes a package request list and reduces it into the equivalent
    optimal form, merging any requests for common packages. Order of packages
    is retained.
    """
    def __init__(self, package_requests):
        """Create a PackageRequestList.

        Args:
            package_requests: List of PackageRangeStatement objects.
        """
        self.package_requests_ = None
        self.conflict_ = None
        self.requests_dict = {}
        self.request_fams = set()
        self.conflict_request_fams = set()

        for req in package_requests:
            existing_req = self.requests_dict.get(req.name)
            if existing_req:
                merged_req = existing_req.merged(req)
                if merged_req is None:
                    self.conflict_ = (existing_req, req)
                    return
                else:
                    self.requests_dict[req.name] = merged_req
            else:
                self.requests_dict[req.name] = req

        names = set()
        self.package_requests_ = []
        for req in package_requests:
            if req.name not in names:
                names.add(req.name)
                self.package_requests_.append(self.requests_dict[req.name])
                if req.conflict:
                    self.conflict_request_fams.add(req.name)
                else:
                    self.request_fams.add(req.name)

    @property
    def package_requests(self):
        """Returns optimised list of package requests, or None if the request
        is not possible due to conflicts.
        """
        return self.package_requests_

    @property
    def conflict(self):
        """Get the requirement conflict, if any.

        Returns:
            None if there is no conflict, otherwise a 2-tuple containing the
            conflicting PackageRangeStatement objects.
        """
        return self.conflict_

    def get(self, pkg_name):
        """Returns the PackageRangeStatement for the given package, or None.
        """
        return self.requests_dict.get(pkg_name)

    def __len__(self):
        return len(self.package_requests_)

    def __str__(self):
        if self.conflict_:
            s1 = str(self.conflict_[0]) or "''"
            s2 = str(self.conflict_[1]) or "''"
            return "%s <--!--> %s" % (s1,s2)
        else:
            return ' '.join(str(x) for x in self.package_requests_)



class Reduction(_Common):
    def __init__(self, name, version, variant_index, dependency,
                 conflicting_request):
        self.name = name
        self.version = version
        self.variant_index = variant_index
        self.dependency = dependency
        self.conflicting_request = conflicting_request

    def reducee_str(self):
        stmt = PackageStatement.construct(self.name, self.version)
        idx_str = '' if self.variant_index is None \
            else "[%d]" % self.variant_index
        return str(stmt) + idx_str

    def __str__(self):
        return "removed %s (dep(%s) <--!--> %s)" \
            % (self.reducee_str(), self.dependency, self.conflicting_request)



class FailureReason(object):
    pass



class TotalReduction(FailureReason):
    def __init__(self, reductions):
        self.reductions = reductions



class PackageVariant(_Common):
    """A variant of a package."""
    def __init__(self, name, version, path, requires, index=None):
        """Create a package variant.

        Args:
            name: Name of package.
            version: The package version, as a Version object.
            path: Path to the root of the package (not incl. variant subdir).
            requires: List of strings representing the package dependencies.
            index: Zero-based index of the variant within this package. If None,
                this package does not have variants.
        """
        self.name = name
        self.version = version
        self.path = path
        self.index = index

        reqs = [PackageRangeStatement(x) for x in requires]
        self.requires_list = PackageRequestList(reqs)

        if self.requires_list.conflict:
            raise ResolveError(("The package at %s has an internal requirements "
                               "conflict: %s") % (path, str(self.requires_list)))

    @property
    def request_fams(self):
        return self.requires_list.request_fams

    @property
    def conflict_request_fams(self):
        return self.requires_list.conflict_request_fams

    def get(self, pkg_name):
        return self.requires_list.get(pkg_name)

    def __eq__(self):
        return (self.version == other.version) and (self.index == other.index)

    def __str__(self):
        stmt = PackageStatement.construct(self.name, self.version)
        variant_str = '' if self.index is None else "[%d]" % self.index
        return "%s%s" % (str(stmt), variant_str)



class _PackageVariantList(_Common):
    """A sorted list of package variants."""
    def __init__(self, package_name, package_paths=None):
        self.package_name = package_name
        self.variants = []
        for pkg in iter_packages_in_range(package_name,
                                          latest=False,
                                          paths=package_paths):
            path = pkg.base
            version = pkg.version
            requires = pkg.metadata["requires"] or []
            variants = pkg.metadata["variants"] or []

            if variants:
                variants_ = []
                for i,v in enumerate(variants):
                    variant_requires = v
                    requires_ = requires + variant_requires
                    variant = PackageVariant(name=package_name,
                                             version=version,
                                             path=path,
                                             requires=requires_,
                                             index=i)
                    variants_.append(variant)

                self.variants.extend(reversed(variants_))
            else:
                variant = PackageVariant(name=package_name,
                                         version=version,
                                         path=path,
                                         requires=requires)
                self.variants.append(variant)

        if not self.variants:
            raise PkgFamilyNotFoundError("Package family could not be found: %s"
                                         % str(package_name))

    def get_intersection(self, range):
        variants = []
        for variant in self.variants:
            if variant.version in range:
                variants.append(variant)

        return variants or None

    def dump(self):
        print self.package_name
        print '\n'.join(str(x) for x in self.variants)

    def __str__(self):
        return "%s[%s]" % (self.package_name,
                           ' '.join(str(x) for x in self.variants))



# print shortened version of '==X|==Y|==Z' ranged requests
def _short_req_str(package_request):
    reqstr = None
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
        return bool(self.common_fams - self.extracted_fams)

    def intersect(self, range):
        """Remove variants whos version fall outside of the given range."""
        self.pr("intersecting %s wrt range '%s'..." % (str(self), str(range)))
        variants = [x for x in self.variants if x.version in range]
        if not variants:
            return None
        elif len(variants) < len(self.variants):
            slice = self._copy(variants)
            return slice
        else:
            return self

    def reduce(self, package_request):
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
            self.pr("reducing %s wrt %s..." % (str(self), reqstr))

        variants = []
        reductions = []

        for variant in self.variants:
            req = variant.get(package_request.name)
            if req and req.conflicts_with(package_request):
                if self.pr:
                    red = Reduction(name=variant.name,
                                    version=variant.version,
                                    variant_index=variant.index,
                                    dependency=req,
                                    conflicting_request=package_request)
                    reductions.append(red)
                    self.pr(str(red))
                continue

            variants.append(variant)

        if not variants:
            return (None, reductions)
        elif reductions:
            slice = self._copy(variants)
            return (slice, reductions)
        else:
            return (self, [])

    def extract(self):
        """Extract a common dependency.

        Note that conflict dependencies are never extracted, they are always
        resolved via reduction.
        """
        extractable = self.common_fams - self.extracted_fams
        if extractable:
            fam = iter(extractable).next()
            ranges = []

            for variant in self.variants:
                req = variant.get(fam)
                ranges.append(req.range)

            slice = copy.copy(self)
            slice.extracted_fams = self.extracted_fams | set([fam])

            range = ranges[0].get_union(ranges[1:])
            common_req = PackageRangeStatement.construct(fam, range)
            return (slice,common_req)
        else:
            return (self,None)

    def split(self):
        """Split the slice."""
        assert(not self.extractable)
        if len(self.variants) == 1:
            return None
        else:
            latest_variant = self.variants[-1]
            split_fams = None
            nleading = 1

            if len(self.variants) > 2:
                fams = latest_variant.request_fams - self.extracted_fams
                if fams:
                    other_variants = reversed(self.variants[:-1])
                    for j,variant in enumerate(other_variants):
                        next_fams = variant.request_fams & fams
                        if next_fams:
                            fams = next_fams
                        else:
                            split_fams = fams
                            nleading = 1+j
                            break

            slice = self._copy(self.variants[-nleading:])
            next_slice = self._copy(self.variants[:-nleading])

            if self.pr:
                s = "split %s into %s and %s " \
                    % (str(self), str(slice), str(next_slice))
                if split_fams is None:
                    s += "on leading variant"
                else:
                    s += "on %d leading variants with common dependencies: %s" \
                        % (nleading, ", ".join(split_fams))
                self.pr(s)

            return (slice,next_slice)

    def dump(self):
        print self.package_name
        print '\n'.join(str(x) for x in self.variants)

    def _copy(self, new_variants):
        slice = copy.copy(self)
        slice.variants = new_variants
        slice.extracted_fams = set()
        slice._update()
        return slice

    def _update(self):
        # range
        versions = set(x.version for x in self.variants)
        self.range = VersionRange.from_versions(versions)

        # family-related
        self.common_fams = set(self.variants[0].request_fams)
        self.fam_requires = set()

        for variant in self.variants:
            self.common_fams &= variant.request_fams
            self.fam_requires |= variant.request_fams
            self.fam_requires |= variant.conflict_request_fams

    def __len__(self):
        return len(self.variants)

    def __str__(self):
        """
        foo[2..6(3:4)]* means, 3 versions, 4 variants in 2..6, and at least one
            family can still be extracted.
        foo[2..6(2)] means, 2 versions in 2..6.
        foo[==2[1,2]] means, 1st and 2nd variants of exact version foo-2.
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



# TODO manage timestamps, reloading from disk on change, etc
class _PackageVariantCache(object):
    def __init__(self, package_paths=None):
        self.package_paths = package_paths or settings.packages_path
        self.variant_lists = {}  # {package-name: _PackageVariantList}

    def get_variant_slice(self, package_name, range):
        variant_list = self.variant_lists.get(package_name)
        if variant_list is None:
            variant_list = _PackageVariantList(package_name, self.package_paths)
            self.variant_lists[package_name] = variant_list

        variants = variant_list.get_intersection(range)
        if not variants:
            return None

        return _PackageVariantSlice(package_name,
                                    variants=variants)



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
            self.variant_slice = solver._get_variant_slice(package_request.name,
                                                           package_request.range)
            if self.variant_slice is None:
                req = PackageRangeStatement.construct(package_request.name,
                                                      package_request.range)
                raise PackageNotFoundError("Package could not be found: %s" % str(req))

            self._update()

    def intersect(self, range):
        """Intersect this scope with a package range.

        Returns:
            A new copy of this scope, with variants whos version fall outside of
            the given range removed. If there were no removals, self is returned.
            If all variants were removed, None is returned.
        """
        new_slice = None

        if self.package_request.conflict:
            if self.package_request.range is None:
                return self
            else:
                new_range = range - self.package_request.range
                if new_range is not None:
                    new_slice = self.solver._get_variant_slice( \
                        self.package_name, new_range)
        else:
            new_slice = self.variant_slice.intersect(range)

        if new_slice is None:
            self.pr("%s intersected with range '%s' resulted in no packages"
                       % (str(self), str(range)))
            return None
        elif new_slice is not self.variant_slice:
            scope = self._copy(new_slice)

            self.pr("%s was intersected to %s by range '%s'"
                     % (str(self), str(scope), str(range)))
            return scope
        else:
            return self

    def reduce(self, package_request):
        """Reduce this scope wrt a package request.

        Returns:
            A (_PackageScope, [Reduction]) tuple, where the scope is a new scope
            copy with reductions applied, or self if there were no reductions,
            or None if the slice was completely reduced.
        """
        if not self.package_request.conflict:
            new_slice,reductions = self.variant_slice.reduce(package_request)

            if new_slice is None:
                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr("%s was reduced to nothing by %s"
                               % (str(self), reqstr))
                    self.pr.br()
                return (None, reductions)
            elif new_slice is not self.variant_slice:
                scope = self._copy(new_slice)

                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr("%s was reduced to %s by %s"
                               % (str(self), str(scope), reqstr))
                    self.pr.br()
                return (scope, reductions)

        return (self, [])

    def extract(self):
        """Extract a common dependency.

        Returns:
            A (_PackageScope, PackageRangeStatement) tuple, containing the new
            scope copy with the extraction, and the extracted package range. If
            no package was extracted, then (self,None) is returned.
        """
        if not self.package_request.conflict:
            new_slice,package_request = self.variant_slice.extract()
            if package_request:
                assert(new_slice is not self.variant_slice)
                scope = copy.copy(self)
                scope.variant_slice = new_slice
                self.pr("extracted %s from %s" % (str(package_request), str(self)))
                return (scope,package_request)

        return (self,None)

    def split(self):
        """Split the scope.

        Returns:
            A (_PackageScope,_PackageScope) tuple, where the first scope is
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
                slice,next_slice = r
                scope = self._copy(slice)
                next_scope = self._copy(next_slice)
                return (scope,next_scope)

    def _copy(self, new_slice):
        scope = copy.copy(self)
        scope.variant_slice = new_slice
        scope._update()
        return scope

    def _is_solved(self):
        return bool(self.package_request.conflict) \
            or ((len(self.variant_slice) == 1) \
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
            self.package_request = PackageRangeStatement.construct( \
                self.package_name, self.variant_slice.range)

    def __str__(self):
        return str(self.variant_slice) if self.variant_slice \
            else str(self.package_request)



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
        self.extractions = None
        self.solver = solver
        self.pr = solver.pr
        self.status = "pending"

        self.scopes = []
        for package_request in package_requests:
            scope = _PackageScope(package_request, solver=solver)
            self.scopes.append(scope)

        self.pending_reducts = set()  # list of (reducer,reducee) tuples
        for i in range(len(self.scopes)):
            for j in range(len(self.scopes)):
                if i!=j:
                    self.pending_reducts.add((i,j))

    def solve(self):
        """Attempt to solve the phase."""
        if self.status != "pending":
            return self

        scopes = self.scopes[:]
        failure_reason = None
        extractions = set()
        pending_reducts = self.pending_reducts.copy()

        def _create_phase(status):
            phase = copy.copy(self)
            phase.scopes = scopes
            phase.failure_reason = failure_reason
            phase.extractions = extractions
            phase.pending_reducts = set()
            phase.status = status
            return phase

        while True:
            # iteratively extract until no more extractions possible
            self.pr.subheader("EXTRACTING:")
            common_requests = []
            for i in range(len(scopes)):
                extracting = True
                while extracting:
                    scope_,common_request = scopes[i].extract()
                    if common_request:
                        common_requests.append(common_request)
                        extractions.add((scopes[i].package_name, common_request.name))
                        edges.append(self._g_edge(scopes[i], common_request, "needs"))
                        scopes[i] = scope_
                    else:
                        extracting = False

            if common_requests:
                request_list = PackageRequestList(common_requests)
                if request_list.conflict:
                    return _create_phase("failed")
                else:
                    self.pr("merged extractions: %s" % str(request_list))
                    if len(request_list) < len(common_requests):
                        for req in request_list.package_requests:
                            src_reqs = [x for x in common_requests
                                        if x.name == req.name]
                            if len(src_reqs) > 1:
                                for src_req in src_reqs:
                                    if src_req != req:
                                        edges.append(self._g_edge(src_req, req))

                # do intersections with existing scopes
                self.pr.subheader("INTERSECTING:")
                req_fams = []

                for i,scope in enumerate(scopes):
                    req = request_list.get(scope.package_name)
                    if req is not None:
                        scope_ = scope.intersect(req.range)
                        req_fams.append(req.name)

                        if scope_ is None:
                            # is this ever hit?
                            assert("JUST CHECKING!")
                            return _create_phase("failed")
                        elif scope_ is not scope:
                            scopes[i] = scope_
                            for j in range(len(scopes)):
                                if j!=i:
                                    pending_reducts.add((i,j))

                            if scope.package_request.conflict:
                                # conflict-range + range merge causes a package read
                                req_int = scope.package_request.merged(req)
                                edges.append(self._g_edge(scope, req_int))
                                edges.append(self._g_edge(req, req_int))
                                edges.append(self._g_edge(req_int, scope_, "read"))
                            else:
                                edges.append(self._g_edge(req, scope_))
                                edges.append(self._g_edge(scope, scope_))

                        elif scope.package_request != req:
                            edges.append(self._g_edge(req, scope))

                # add new scopes
                self.pr.subheader("ADDING:")
                new_reqs = [x for x in request_list.package_requests \
                    if x.name not in req_fams]

                if new_reqs:
                    n = len(scopes)

                    for req in new_reqs:
                        scope = _PackageScope(req, solver=self.solver)
                        scopes.append(scope)
                        if not req.conflict:
                            edges.append(self._g_edge(req, scope, "read"))
                        self.pr("added %s" % str(scope))

                    m = len(new_reqs)
                    for i in range(n,n+m):
                        for j in range(n+m):
                            if i!=j:
                                pending_reducts.add((i,j))

                    for i in range(n):
                        for j in range(n,n+m):
                            pending_reducts.add((i,j))

            if not pending_reducts:
                break

            # iteratively reduce until no more reductions possible
            self.pr.subheader("REDUCING:")
            while pending_reducts:
                for i,j in pending_reducts.copy():
                    new_scope,reductions = scopes[j].reduce(scopes[i].package_request)
                    if new_scope is None:
                        failure_reason = TotalReduction(reductions)
                        return _create_phase("failed")
                    elif new_scope is not scopes[j]:
                        edges.append(self._g_edge(scopes[j], new_scope, "reduce"))
                        scopes[j] = new_scope
                        for i in range(len(scopes)):
                            if i!=j:
                                pending_reducts.add((j,i))

                    pending_reducts -= set([(i,j)])

        # create new phase
        status = "solved" if phase._is_solved() else "exhausted"
        return _create_phase(status)

    def finalise(self):
        """Remove conflict requests, and order packages wrt dependency and
        request order.

        Returns:
            A new copy of the phase with conflict requests removed and packages
            correctly ordered.
        """
        phase = copy.copy(self)
        phase.scopes = [x for x in phase.scopes if not x.package_request.conflict]
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
        which contains a package scope with a common dependency. This dependency
        can now be intersected with the current resolve, thus progressing it.

        Returns:
            A 2-tuple of _ResolvePhase objects, where the first phase is the
            best contender for resolving.
        """
        assert(self.status == "exhausted")

        scopes = []
        next_scopes = []
        split = None

        for i,scope in enumerate(self.scopes):
            if split is None:
                r = scope.split()
                if r is not None:
                    scope_,next_scope = r
                    scopes.append(scope_)
                    next_scopes.append(next_scope)
                    split = i
                    continue

            scopes.append(scope)
            next_scopes.append(scope)

        phase = copy.copy(self)
        phase.scopes = scopes
        phase.status = "pending"

        for i in range(len(phase.scopes)):
            if i!=split:
                phase.pending_reducts.add((split,i))

        next_phase = copy.copy(phase)
        next_phase.scopes = next_scopes
        return (phase,next_phase)

    def get_graph(self):
        """Get the resolve graph.

        The resolve graph shows what packages were resolved, and the
        relationships between them. A failed phase also has a graph, which
        will shows the conflict(s) that caused the resolve to fail.

        Returns:
            A pygraph.digraph object.
        """
        edges = set()
        edge_types = {}
        src_nodes = set()
        dest_nodes = set()
        request_nodes = set()
        requires_nodes = set()
        solved_nodes = set()
        scopes = dict((x.package_name,x) for x in self.scopes)

        def _add_edge(src, dest, type_=None):
            src_nodes.add(src)
            dest_nodes.add(dest)
            e = (src,dest)
            edges.add(e)
            if type_:
                edge_types[e] = type_

        def _str_scope(scope):
            variant = scope._get_solved_variant()
            return str(variant) if variant else str(scope).replace('*','')

        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                solved_nodes.add(str(variant))

        for req in self.package_requests:
            if not req.conflict:
                scope_ = scopes.get(req.name)
                if scope_:
                    req_str = str(req)
                    _add_edge(req_str, _str_scope(scope_))
                    variant_ = scope_._get_solved_variant()
                    if variant_:
                        request_nodes.add(req_str)

        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                for req in variant.requires_list.package_requests:
                    if not req.conflict:
                        req_str = str(req)
                        requires_nodes.add(req_str)
                        _add_edge(str(variant), req_str)

                        scope_ = scopes.get(req.name)
                        if scope_:
                            _add_edge(req_str, _str_scope(scope_))

        for src_fam,dest_fam in self.extractions:
            scope_src = scopes.get(src_fam)
            scope_dest = scopes.get(dest_fam)
            if scope_src and scope_dest:
                str_src = _str_scope(scope_src)
                str_dest = _str_scope(scope_dest)
                if str_dest not in dest_nodes:
                    _add_edge(str_src, str_dest)

        fr = self.failure_reason
        if fr:
            if isinstance(fr, TotalReduction):
                for red in fr.reductions:
                    scope = scopes.get(red.name)
                    str_scope = _str_scope(scope)
                    confl_scope = scopes.get(red.conflicting_request.name)
                    str_confl_scope = _str_scope(confl_scope)

                    str_reduct = "%s requires %s" \
                                 % (red.reducee_str(), str(red.dependency))
                    _add_edge(str_scope, str_reduct, "depends")
                    _add_edge(str_reduct, str_confl_scope, "conflicts")

        node_color = settings.graph_node_color
        request_color = settings.graph_request_color
        solved_color = settings.graph_solved_color
        node_fontsize = str(settings.graph_node_fontsize)

        nodes = src_nodes | dest_nodes
        g = digraph()

        for n in nodes:
            attrs = [("fontsize", node_fontsize)]
            if n in request_nodes:
                attrs.append(("fillcolor", request_color))
                attrs.append(("style", '"filled,dashed"'))
            elif n in solved_nodes:
                attrs.append(("fillcolor", solved_color))
                attrs.append(("style", "filled"))
            elif n in requires_nodes:
                attrs.append(("fillcolor", node_color))
                attrs.append(("style", '"filled,dashed"'))
            else:
                attrs.append(("fillcolor", node_color))
                attrs.append(("style", "filled"))

            g.add_node(n, attrs=attrs)

        for e in edges:
            g.add_edge(e)
            g.add_edge_attribute(e, ("arrowsize", "0.5"))
            type_ = edge_types.get(e)
            if type_:
                if type_ == "depends":
                    g.add_edge_attribute(e, ("style", "dashed"))
                elif type_ == "conflicts":
                    g.set_edge_label(e, "CONFLICTS")
                    g.add_edge_attribute(e, ("style", "bold"))
                    g.add_edge_attribute(e, ("color", "red"))
                    g.add_edge_attribute(e, ("fontcolor", "red"))

        return g

    def _g_edge(self, src, dest, label=''):
        src_ = str(src).replace('*','')
        dest_ = str(dest).replace('*','')
        return (src_, dest_, label)

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
    def __init__(self, package_requests, package_paths=None,
                 package_cache=None, verbose=True):
        """Create a Solver.

        Args:
            package_requests: List of PackageRangeStatement objects
                representing the request.
            package_paths: List of paths to search for pkgs, defaults to
                settings.packages_path.
            package_cache: _PackageVariantCache object used for caching package
                definition file disk reads. If None, an internal cache is used.
        """
        self.package_paths = package_paths or settings.packages_path
        self.request_list = None
        self.pr = _Printer(verbose)
        self.phase_stack = []
        self.solve_count = 0
        self.depth_counts = {}
        self.sat_solve_time = 0.0
        self.solve_time = 0.0
        self.load_time = 0.0
        self.package_cache = package_cache
        self.solve_begun = False

        if self.package_cache is None:
            self.package_cache = _PackageVariantCache(self.package_paths)

        # optimise the request
        self.pr("request: %s" % ' '.join(str(x) for x in package_requests))
        self.request_list = PackageRequestList(package_requests)
        if self.request_list.conflict:
            req1,req2 = self.request_list.conflict
            self.pr("conflict in request: %s <--!--> %s" % (str(req1), str(req2)))
            phase = _ResolvePhase(package_requests, solver=self)
            phase.status = "failed"
            self._push_phase(phase)
            return
        else:
            self.pr("merged request: %s" % ' '.join(str(x) \
                for x in self.request_list.package_requests))

        # create the initial phase
        phase = _ResolvePhase(self.request_list.package_requests, solver=self)
        self._push_phase(phase)

    @property
    def status(self):
        """Return the current status of the solve. One of:
        solved - the resolve has completed successfully.
        failed - the resolve is not possible.
        unsolved - the resolve is unfinished.
        """
        st = self.phase_stack[-1].status
        if len(self.phase_stack) > 1:
            return "solved" if st == "solved" else "unsolved"
        else:
            return "unsolved" if st in ("pending","exhausted") else st

    @property
    def num_solves(self):
        """Return the number of resolve phases that have been executed."""
        return self.solve_count

    @property
    def resolved_packages(self):
        """Return a list of PackageVariant objects, or None if the resolve did
        not complete or was unsuccessful.
        """
        if (self.status != "solved"):
            return None

        final_phase = self.phase_stack[-1]
        return final_phase._get_solved_variants()

    def get_graph(self):
        return self.phase_stack[-1].get_graph()

    def reset(self):
        """Reset the solver, removing any current solve."""
        phase = _ResolvePhase(self.request_list.package_requests, solver=self)
        self.pr("resetting...")
        self.solve_begun = False
        self.sat_solve_time = 0.0
        self.solve_time = 0.0
        self.load_time = 0.0
        self.phase_stack = []
        self._push_phase(phase)

    def solve(self):
        """Attempt to solve the request.
        """
        if self.solve_begun:
            raise ResolveError("cannot run solve() on a solve that has "
                               "already been started")
        self.sat_solve_time = 0.0
        self.solve_time = 0.0
        self.load_time = 0.0

        # iteratively solve phases
        while self.status == "unsolved":
            self.solve_step()

    def solve_step(self):
        """Perform a single step of the native (non-SAT) solver.
        """
        self.solve_begun = True
        if self.status != "unsolved":
            return

        self.pr.header("SOLVE #%d..." % (self.solve_count+1))
        start_time = time.time()
        phase = self._pop_phase()

        if phase.status == "failed":  # a previously failed phase
            self.pr("discarded failed phase, fetching previous unsolved phase...")
            phase = self._pop_phase()

        if phase.status == "exhausted":
            self.pr.subheader("SPLITTING:")
            phase,next_phase = phase.split()
            self._push_phase(next_phase)
            self.pr("new phase: %s" % str(phase))

        if phase._is_solved():
            new_phase = phase
            new_phase.status = "solved"
        else:
            new_phase = phase.solve()

        self.solve_count += 1
        self.pr.subheader("RESULT:")

        if new_phase.status == "failed":
            self.pr("phase failed to resolve")
            self._push_phase(new_phase)
            if len(self.phase_stack) == 1:
                self.pr("FAIL: there is no solution")
        elif new_phase.status == "solved":
            self._finalise_solve(new_phase)
            self.pr("SUCCESS")
        else:
            assert(new_phase.status == "exhausted")
            self._push_phase(new_phase)

        end_time = time.time()
        self.solve_time += (end_time - start_time)

    def sat_solve_step(self):
        """Perform a resolve using the SAT solver."""
        self.solve_begun = True
        if self.status != "unsolved":
            return

        # only run SAT on an exhausted phase, this first narrows the scope of
        # possible packages to as small as possible.
        if self.phase_stack[-1].status != "exhausted":
            self.solve_step()
        if self.status != "unsolved":
            return

        self.pr.header("SOLVE #%d (SAT)..." % (self.solve_count+1))
        raise NotImplemented

    def _get_variant_slice(self, package_name, range):
        start_time = time.time()
        slice = self.package_cache.get_variant_slice(package_name, range)
        slice.pr = self.pr
        end_time = time.time()
        self.load_time += (end_time - start_time)
        return slice

    def dump(self):
        rows = []
        for i,phase in enumerate(self.phase_stack):
            rows.append((self._depth_label(i), phase.status, str(phase)))

        print "status: %s" % self.status
        print "initial request: %s" % str(self.request_list)
        print '\n'.join(columnise(rows))

    def _finalise_solve(self, solved_phase):
        phase = solved_phase.finalise()
        self._push_phase(phase)

    def _push_phase(self, phase):
        depth = len(self.phase_stack)
        count = self.depth_counts.get(depth, -1) + 1
        self.depth_counts[depth] = count
        self.phase_stack.append(phase)

        if self.pr:
            dlabel = self._depth_label()
            self.pr("pushed %s: %s" % (dlabel, str(phase)))

    def _pop_phase(self):
        dlabel = self._depth_label()
        phase = self.phase_stack.pop()
        self.pr("popped %s: %s" % (dlabel, str(phase)))
        return phase

    def _depth_label(self, depth=None):
        if depth is None:
            depth = len(self.phase_stack) - 1
        count = self.depth_counts[depth]
        return "{%d,%d}" % (depth,count)

    def __str__(self):
        return "%s %s %s" % (self.status,
                             self._depth_label(),
                             str(self.phase_stack[-1]))
