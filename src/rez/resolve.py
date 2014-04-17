"""
The dependency resolving module.
"""
from rez.backport.total_ordering import total_ordering
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PkgFamilyNotFoundError
from rez.version import VersionRange
from rez.packages import PackageRangeStatement, iter_packages_in_range
from rez.util import columnise
from rez.settings import settings
import copy



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

    def pr(self, txt):
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

    def __str__(self):
        if self.conflict_:
            s1 = str(self.conflict_[0]) or "''"
            s2 = str(self.conflict_[1]) or "''"
            return "%s <--!--> %s" % (s1,s2)
        else:
            return ' '.join(str(x) for x in self.package_requests_)



@total_ordering
class _PackageVariant(_Common):
    """A variant of a package."""
    def __init__(self, version, path, requires, index=None):
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

    def __lt__(self, other):
        return (self.version, -(self.index or 0)) \
               < (other.version, -(other.index or 0))

    def __eq__(self):
        return (self.version == other.version) and (self.index == other.index)

    def __str__(self):
        variant_str = '' if self.index is None else "[%d]" % self.index
        return "%s%s" % (str(self.version) or "''", variant_str)



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
                for i,v in enumerate(variants):
                    variant_requires = v
                    requires_ = requires + variant_requires
                    variant = _PackageVariant(version=version,
                                              path=path,
                                              requires=requires_,
                                              index=i)
                    self.variants.append(variant)
            else:
                variant = _PackageVariant(version=version,
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
    def __init__(self, package_name, variants, printer):
        self.package_name = package_name
        self.variants = variants
        self.pr = printer
        self.range = None

        # family tracking
        self.extracted_fams = set()
        self.fam_requires = None
        self.common_fams = None

        self._update()

    def intersect(self, range):
        """Remove variants whos version fall outside of the given range."""
        self.pr.pr("intersecting %s wrt range '%s'..." % (str(self), str(range)))
        variants = [x for x in self.variants if x.version in range]
        if not variants:
            return None
        elif len(variants) < len(self.variants):
            slice = copy.copy(self)
            slice.variants = variants
            slice._update()
            return slice
        else:
            return self

    def reduce(self, package_request):
        """Remove variants whos dependencies conflict with the given package
        request."""
        if (package_request.range is None) or \
            (package_request.name not in self.fam_requires):
            return self

        if self.pr:
            reqstr = _short_req_str(package_request)
            self.pr.pr("reducing %s wrt %s..." % (str(self), reqstr))

        variants = []
        for variant in self.variants:
            req = variant.get(package_request.name)
            if req and req.merged(package_request) is None:
                self.pr.pr("removed %s-%s (dep(%s) <--!--> %s)" \
                         % (self.package_name, str(variant), str(req), reqstr))
                continue

            variants.append(variant)

        if not variants:
            return None
        elif len(variants) < len(self.variants):
            slice = copy.copy(self)
            slice.variants = variants
            slice._update()
            return slice
        else:
            return self

    def extract(self):
        """Extract a common dependency."""
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
        [foo==2]* means, exact version foo-2, families still to extract.
        [foo==2] means a resolved package.
        """
        nvariants = len(self.variants)
        if nvariants == 1:
            s = "[%s==%s]" % (self.package_name, str(self.variants[0].version))
        else:
            nversions = len(set(x.version for x in self.variants))
            verstr = "%d" % nvariants if (nversions == nvariants) \
                else "%d:%d" % (nversions, nvariants)
            span = self.range.span()
            s = "%s[%s(%s)]" % (self.package_name, str(span), verstr)

        strextr = '*' if (self.common_fams - self.extracted_fams) else ''
        return s + strextr



class _PackageScope(_Common):
    """Contains possible solutions for a package, such as a list of variants,
    or a conflict range. As the resolve progresses, package scopes are narrowed
    down.
    """
    def __init__(self, package_request, resolver):
        self.package_name = package_request.name
        self.resolver = resolver
        self.variant_slice = None
        self.pr = resolver.pr

        if package_request.conflict:
            self.package_request = package_request
        else:
            self.variant_slice = resolver._get_variant_slice(package_request.name,
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
                    new_slice = self.resolver._get_variant_slice( \
                        self.package_name, new_range)
        else:
            new_slice = self.variant_slice.intersect(range)

        if new_slice is None:
            self.pr.pr("%s intersected with range '%s' resulted in no packages"
                       % (str(self), str(range)))
            return None
        elif new_slice is not self.variant_slice:
            scope = copy.copy(self)
            scope.variant_slice = new_slice
            scope._update()

            self.pr.pr("%s was intersected to %s by range '%s'"
                     % (str(self), str(scope), str(range)))
            return scope
        else:
            return self

    def reduce(self, package_request):
        """Reduce this scope wrt a package request.

        Returns:
            A new copy of this scope, with variants whos dependencies conflict
            with the given package request removed. If there were no removals,
            self is returned. If all variants were removed, None is returned.
        """
        if not self.package_request.conflict:
            new_slice = self.variant_slice.reduce(package_request)

            if new_slice is None:
                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr.pr("%s was reduced to nothing by %s"
                               % (str(self), reqstr))
                    self.pr.br()
                return None
            elif new_slice is not self.variant_slice:
                scope = copy.copy(self)
                scope.variant_slice = new_slice
                scope._update()

                if self.pr:
                    reqstr = _short_req_str(package_request)
                    self.pr.pr("%s was reduced to %s by %s"
                               % (str(self), str(scope), reqstr))
                    self.pr.br()
                return scope

        return self

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
                self.pr.pr("extracted %s from %s" % (str(package_request), str(self)))
                return (scope,package_request)

        return (self,None)

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
    new phases replace this phase on the resolver's phase stack.

    If the resolve phase gets to a point where every package scope is solved,
    then the entire resolve is considered to be solved.
    """
    def __init__(self, scopes, resolver):
        self.scopes = scopes
        self.resolver = resolver
        self.pr = resolver.pr
        self.dirty_fams = set(x.package_name for x in self.scopes)
        self.status = "pending"

    def solve(self):
        """Attempt to solve the phase."""
        if self.status != "pending":
            return self

        assert(self.dirty_fams)
        scopes = self.scopes

        while self.dirty_fams:
            # iteratively reduce until no more reductions possible
            self.pr.subheader("REDUCING:")
            while self.dirty_fams:
                fams_ = set()

                for scope in scopes[:]:
                    if scope.package_name in self.dirty_fams:
                        scope_changed = False
                        scopes_ = []

                        for scope_ in scopes:
                            if scope_ is scope:
                                scopes_.append(scope_)
                            else:
                                new_scope = scope_.reduce(scope.package_request)
                                if new_scope is None:
                                    return None  # FAIL
                                else:
                                    scopes_.append(new_scope)
                                    if new_scope is not scope_:
                                        fams_.add(new_scope.package_name)
                                        scope_changed = True

                        fams_ -= set([scope.package_name])
                        if scope_changed:
                            scopes = scopes_
                self.dirty_fams = fams_

            # iteratively extract until no more extractions possible
            self.pr.subheader("EXTRACTING:")
            common_requests = []
            scopes_ = []

            for scope in scopes:
                scope_,common_request = scope.extract()
                if common_request:
                    common_requests.append(common_request)
                    scopes_.append(scope_)
                else:
                    assert(scope_ is scope)
                    scopes_.append(scope_)

            if common_requests:
                scopes = scopes_

                request_list = PackageRequestList(common_requests)
                if request_list.conflict:
                    return None  # FAIL
                else:
                    self.pr.pr("merged extractions: %s" % str(request_list))

                    # do intersections with existing scopes
                    self.pr.subheader("INTERSECTING:")
                    for package_request in request_list.package_requests:
                        fam = package_request.name
                        scopes_ = []

                        for scope in scopes:
                            if scope.package_name == fam:
                                scope_ = scope.intersect(package_request.range)
                                if scope_ is None:
                                    return None  # FAILS
                                else:
                                    scopes_.append(scope_)
                                    if scope_ is not scope:
                                        self.dirty_fams.add(fam)
                            else:
                                scopes_.append(scope)
                        scopes = scopes_

                    # add new scopes
                    self.pr.subheader("ADDING:")
                    existing_fams = set(x.package_name for x in scopes)

                    for package_request in request_list.package_requests:
                        fam = package_request.name
                        if fam not in existing_fams:
                            scope = _PackageScope(package_request,
                                                  resolver=self.resolver)
                            scopes.append(scope)
                            self.pr.pr("added %s" % str(scope))
                            self.dirty_fams.add(fam)

        # create new phase
        if scopes is self.scopes:
            self.status = "exhausted"
            return self
        else:
            phase = copy.copy(self)
            phase.scopes = scopes

            # if all scopes are either conflicts or contain a single variant,
            # then the phase is solved.
            for scope in scopes:
                if not scope.package_request.conflict \
                    and len(scope.variant_slice) > 1:
                    phase.status = "exhausted"
                    return phase

            phase.status = "solved"
            return phase

    def remove_conflict_requests(self):
        """Remove conflict requests from the phase (eg '!foo-5').

        Returns:
            A new copy of the phase with conflict requests removed.
        """
        phase = copy.copy(self)
        phase.scopes = [x for x in phase.scopes if not x.package_request.conflict]
        return phase

    def split(self):
        """Split the phase.

        When a phase is unsolved, it gets split into a pair of phases to be
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

    def __str__(self):
        scopes_str = ' '.join(str(x) for x in self.scopes)
        return ' '.join(str(x) for x in self.scopes)



class Resolver(_Common):
    """Package resolver.

    A package resolver takes a list of package requests (the 'request'), then
    runs a resolve algorithm in order to determine the 'resolve' - the list of
    non-conflicting packages that include all dependencies.
    """
    def __init__(self, package_requests, package_paths=None, verbose=True):
        """Create a Resolver.

        Args:
            package_requests: List of PackageRangeStatement objects.
            package_paths: List of paths to search for pkgs, defaults to
                settings.packages_path.
        """
        self.package_paths = package_paths or settings.packages_path
        self.pr = _Printer(verbose)
        self.phase_stack = []
        self.solve_count = 0
        self.depth_counts = {}
        self.variant_lists = {}  # {package-name: _PackageVariantList}

        def _phase(reqs):
            scopes = []
            for req in reqs:
                scope = _PackageScope(req, resolver=self)
                scopes.append(scope)
            return _ResolvePhase(scopes, resolver=self)

        # optimise the request
        self.pr.pr("request: %s" % ' '.join(str(x) for x in package_requests))
        reqlist = PackageRequestList(package_requests)
        if reqlist.conflict:
            req1,req2 = reqlist.conflict
            self.pr.pr("conflict in request: %s <--!--> %s" % (str(req1), str(req2)))
            phase = _phase(package_requests)
            phase.status = "failed"
            self._push_phase(phase)
            return
        else:
            self.pr.pr("merged request: %s"
                       % ' '.join(str(x) for x in reqlist.package_requests))

        # create the initial phase
        phase = _phase(reqlist.package_requests)
        self._push_phase(phase)

    @property
    def status(self):
        if len(self.phase_stack) > 1:
            return "unsolved"
        else:
            st = self.phase_stack[-1].status
            return "unsolved" if st in ("pending","exhausted") else st

    @property
    def num_solves(self):
        """Return the number of resolve phases that have been executed."""
        return self.solve_count

    @property
    def resolved_packages(self):
        """Return a list of resolved packages, or None if the resolve did not
        complete or was unsuccessful.
        """
        if (not self.succeeded):
            return None

        final_phase = self.phase_stack[-1]
        # TODO
        #return final_phase.resolved_packages

    def solve(self, max_steps=None):
        """Attempt to solve the resolve.

        If max_steps is not None, and the solve is not completed after calling
        this method, then solve() can be called again to continue progressing
        with the resolve.

        Args:
            max_steps: Perform at most this many solve steps.
        """
        st = self.status
        if st != "unsolved":
            self.pr.pr("solve not executed: status is %s" % st)
            return

        # iteratively solve phases
        while (self.status == "unsolved") and ((max_steps is None) or max_steps):
            dlabel = self._depth_label()
            phase = self.phase_stack.pop()

            if phase.status == "failed":  # a previously failed phase
                self.pr.pr("discarding previous failed phase...")
                phase = self.phase_stack.pop()

            if phase.status == "exhausted":
                if self.pr:
                    self.pr.header("splitting phase %s (%s)..."
                                   % (dlabel, str(phase)))

                phase,next_phase = phase.split()
                self._push_phase(next_phase)

            if self.pr:
                self.pr.header("solving phase %s (%s)..." % (dlabel, str(phase)))

            new_phase = phase.solve()
            self.solve_count += 1
            self.pr.subheader("RESULT:")

            if new_phase is None:
                self.pr.pr("phase %s failed to resolve" % dlabel)
                phase.status = "failed"
                self._push_phase(phase)
                if len(self.phase_stack) == 1:
                    self.pr.pr("FAIL: there is no solution")
            else:
                if self.pr:
                    verb = "unchanged" if new_phase is phase else "changed"
                    self.pr.pr("phase %s was %s" % (dlabel, verb))

                if new_phase.status == "solved":
                    solved_phase = new_phase.remove_conflict_requests()
                    self._push_phase(solved_phase)
                    self.pr.pr("SUCCESS")
                else:
                    assert(new_phase.status == "exhausted")
                    self._push_phase(new_phase)

            if max_steps is not None:
                max_steps -= 1

    def dump(self):
        rows = []
        for i,phase in enumerate(self.phase_stack):
            rows.append((self._depth_label(i), phase.status, str(phase)))

        print "status: %s" % self.status
        print '\n'.join(columnise(rows))

    def _get_variant_slice(self, package_name, range):
        variant_list = self.variant_lists.get(package_name)
        if variant_list is None:
            variant_list = _PackageVariantList(package_name, self.package_paths)
            self.variant_lists[package_name] = variant_list

        variants = variant_list.get_intersection(range)
        if not variants:
            return None

        return _PackageVariantSlice(package_name,
                                    variants=variants,
                                    printer=self.pr)

    def _push_phase(self, phase):
        depth = len(self.phase_stack)
        count = self.depth_counts.get(depth, -1) + 1
        self.depth_counts[depth] = count
        self.phase_stack.append(phase)

        if self.pr:
            dlabel = self._depth_label()
            self.pr.pr("pushed %s: %s" % (dlabel, str(phase)))

    def _depth_label(self, depth=None):
        if depth is None:
            depth = len(self.phase_stack) - 1
        count = self.depth_counts[depth]
        return "{%d,%d}" % (depth,count)

    def __str__(self):
        return "%s %s %s" % (self.status,
                             self._depth_label(),
                             str(self.phase_stack[-1]))
