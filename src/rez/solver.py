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
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.algorithms.cycles import find_cycle
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from rez.exceptions import PackageNotFoundError, ResolveError, \
    PackageFamilyNotFoundError
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import VersionedObject, Requirement, \
    RequirementList, extract_family_name_from_requirements
from rez.vendor.enum import Enum
from rez.packages_ import iter_packages
from rez.config import config
from heapq import merge
import copy
import time
import sys
from operator import itemgetter


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


class VariantSorter(object):
    """
    Example of the variant sorting algorithm see test cases in tests_solver for more

    #initial order

    #0    [ foo-4, bar-1, zex-1, bah-1 ]
    #1    [ foo-1, eek-3, zex-2, bah-2 ]
    #2    [ foo-1, bar-3, zex-3, bah-3 ]
    #3    [ foo-3, zex-4, bah-4, eek-3 ]
    #4    [ foo-1, bar-2, zex-5, bah-5 ]
    #5    [ foo-1, bar-4, zex-1, bah-6 ]
    #6    [ foo-3, eek-5, zex-4 ]
    #7    [ bar-4]
    #8    [ bar-2, bah-2 foo-1 ]
    #9    [ bar-4, bah-1, foo-2 ]
    #10   [ bar-4, bah-2 ]
    #11   [ foo-3, zex-5, bah-2, eek-5 ]
    #12   [ foo-1 , eek-1, zex-4, bah-4 ]
    #13   [ bar-3, bah-4 ]

    # request eek zex foo-1+   (fam_requires=eek, zex, foo)

    First group variants per intersecting weight.
     Weight is given by the intersecting teh variant package name with the fam request

                                                IntWeight


    #7    [ bar-4]                                 0
    #10   [ bar-4, bah-2 ]                         0
    #13   [ bar-3, bah-4 ]                         0

    #8    [ bar-2, bah-2 foo-1 ]                   1
    #9    [ bar-4, bah-1, foo-2 ]                  1

    #0    [ foo-4, bar-1, zex-1, bah-1 ]           2
    #2    [ foo-1, bar-3, zex-3, bah-3 ]           2
    #4    [ foo-1, bar-2, zex-5, bah-5 ]           2
    #5    [ foo-1, bar-4, zex-1, bah-6 ]           2

    #1    [ foo-1, eek-3, zex-2, bah-2 ]           3
    #3    [ foo-3, zex-4, bah-4, eek-3 ]           3
    #6    [ foo-3, eek-5, zex-4 ]                  3
    #11   [ foo-3, zex-5, bah-2, eek-5 ]           3
    #12   [ foo-1 , eek-1, zex-4, bah-4 ]          3

    Now sort each variant starting for the one with less weigh by VersionRange of the fam_requires

    Sorting intersecting Weight 0
    -----------------------------
    These variants does not contain any of the fam_requires so the next criteria is get the weight by amount of
     packages. We want the variants  with less packages to be picked first so they have more weight

                                                IntWeight      PackagesWeight


    #7    [ bar-4]                                 0                1

    #10   [ bar-4, bah-2 ]                         0                0
    #13   [ bar-3, bah-4 ]                         0                0

    We still need to sort the variants with PackagesWeight 0
    Take a weighted average of where they appear in all the variants.

    Position Weight is given 1 if found in position 0 , 1/2 in position 1, 1/3 in position 2 and so on

    #10   [ bar-4, bah-2 ]
    #13   [ bar-3, bah-4 ]

    so bar = 2 (1+1) and bah = 1 ( 0.5 + 0.5 ) , so we now sort by bar and in case of tie we sort by bah

                                                IntWeight      PackagesWeight         bar VersionRange

    #13   [ bar-3, bah-4 ]                         0                0                       3

    #10   [ bar-4, bah-2 ]                         0                0                       4

    Sorting by bar VersionRange gives a sorted group so we do not need to sort by bah

    So the group IntWeight 0 sorted is
                                                IntWeight      PackagesWeight         bar VersionRange

    #13   [ bar-3, bah-4 ]                         0                0                       3
    #10   [ bar-4, bah-2 ]                         0                0                       4
    #7    [ bar-4]                                 0                1                       -


    Sorting intersecting Weight 1
    -----------------------------
    We are going to iterate thru the fam_requires in order and sort by VersionRange
     eek and zex won't take any effect on the sorting so only when sorting by foo VersionRange we will remove the tie

                                                IntWeight      foo VersionRange

    #8    [ bar-2, bah-2 foo-1 ]                   1                   1
    #9    [ bar-4, bah-1, foo-2 ]                  1                   2

    So the group IntWeight 1 sorted is

                                                IntWeight      foo VersionRange

    #8    [ bar-2, bah-2 foo-1 ]                   1                  1
    #9    [ bar-4, bah-1, foo-2 ]                  1                  2



    Sorting intersecting Weight 2
    -----------------------------
    We are going to iterate thru the fam_requires in order and sort by VersionRange
     eek does not take any effect so we sort by zex

                                                IntWeight      zex VersionRange

    #0    [ foo-4, bar-1, zex-1, bah-1 ]           2                1
    #5    [ foo-1, bar-4, zex-1, bah-6 ]           2                1
    #2    [ foo-1, bar-3, zex-3, bah-3 ]           2                3
    #4    [ foo-1, bar-2, zex-5, bah-5 ]           2                5


    The variants with zex=1 VersionRange still are tied so we need to sort by the next fam_requires foo


                                                IntWeight      zex VersionRange   foo VersionRange

    #5    [ foo-1, bar-4, zex-1, bah-6 ]           2                 1                   1
    #0    [ foo-4, bar-1, zex-1, bah-1 ]           2                 1                   4

    So the group IntWeight 2 sorted is

                                                IntWeight      zex VersionRange   foo VersionRange

    #5    [ foo-1, bar-4, zex-1, bah-6 ]           2                 1                   1
    #0    [ foo-4, bar-1, zex-1, bah-1 ]           2                 1                   4
    #2    [ foo-1, bar-3, zex-3, bah-3 ]           2                 3                   -
    #4    [ foo-1, bar-2, zex-5, bah-5 ]           2                 5                   -


    Sorting intersecting Weight 3
    -----------------------------
    We are going to iterate thru the fam_requires in order and sort by VersionRange
    Sorting by eek VersionRange yields

                                                IntWeight      eek VersionRange

    #12   [ foo-1 , eek-1, zex-4, bah-4 ]          3                 1

    #1    [ foo-1, eek-3, zex-2, bah-2 ]           3                 3
    #3    [ foo-3, zex-4, bah-4, eek-3 ]           3                 3

    #6    [ foo-3, eek-5, zex-4 ]                  3                 5
    #11   [ foo-3, zex-5, bah-2, eek-5 ]           3                 5


    Group with eek=1 do no need sorting.
    Group with eek=3 versionRange need to keep sorting by the next fam_requires zex which yields

                                                IntWeight      eek VersionRange   zex Version Range

    #1    [ foo-1, eek-3, zex-2, bah-2 ]           3                 3                   2
    #3    [ foo-3, zex-4, bah-4, eek-3 ]           3                 3                   4

    Group with eek=5 versionRange need to keep sorting by the next fam_requires zex which yields


                                                IntWeight      eek VersionRange   zex Version Range

    #6    [ foo-3, eek-5, zex-4 ]                  3                 5                   4
    #11   [ foo-3, zex-5, bah-2, eek-5 ]           3                 5                   5

    Even variant #11 will pull more packages than #6 we prefer #11 which has higher version of the fam_requires


    So the group IntWeight 3 sorted is
                                                IntWeight      eek VersionRange   zex Version Range

    #12   [ foo-1 , eek-1, zex-4, bah-4 ]          3                 1                   -
    #1    [ foo-1, eek-3, zex-2, bah-2 ]           3                 3                   2
    #3    [ foo-3, zex-4, bah-4, eek-3 ]           3                 3                   4
    #6    [ foo-3, eek-5, zex-4 ]                  3                 5                   4
    #11   [ foo-3, zex-5, bah-2, eek-5 ]           3                 5                   5



    The final sorted list
    ----------------------

                                           IntWeight   eek VRange    zex VRange   foo VRange  packageWeight  bar VRange

    #13   [ bar-3, bah-4 ]                   0             -            -             -             0            3
    #10   [ bar-4, bah-2 ]                   0             -            -             -             0            4
    #7    [ bar-4]                           0             -            -             -             1            -
    #8    [ bar-2, bah-2 foo-1 ]             1             -            -             1
    #9    [ bar-4, bah-1, foo-2 ]            1             -            -             2
    #5    [ foo-1, bar-4, zex-1, bah-6 ]     2             -            1             1
    #0    [ foo-4, bar-1, zex-1, bah-1 ]     2             -            1             4
    #2    [ foo-1, bar-3, zex-3, bah-3 ]     2             3            -
    #4    [ foo-1, bar-2, zex-5, bah-5 ]     2             5            -
    #12   [ foo-1 , eek-1, zex-4, bah-4 ]    3             1            -
    #1    [ foo-1, eek-3, zex-2, bah-2 ]     3             3            2
    #3    [ foo-3, zex-4, bah-4, eek-3 ]     3             3            4
    #6    [ foo-3, eek-5, zex-4 ]            3             5            4
    #11   [ foo-3, zex-5, bah-2, eek-5 ]     3             5            5


    """



    def __init__(self, variants, package_requests):
        self.variants = variants
        self.fam_requires = self._curated_package_request(package_requests)

    def _curated_package_request(self, package_request):
        """
        optimization: only leave the fam in the package request that we know can take effect in the sorting
        """
        fam_names_in_variants = set()

        for variant in self.variants:
            fam_names_in_variants.update(extract_family_name_from_requirements(variant))

        fam_requires = extract_family_name_from_requirements(package_request)
        curated_fam_requires = [fam for fam in fam_requires if fam in fam_names_in_variants]

        return curated_fam_requires

    def sort_variants(self):

        return self._sort_variants_by_intersection_weight()

    def _sort_variants_by_intersection_weight(self):
        """
        Slices the list of variants in groups by intersection weight and sort each slice by VersionRange

        The intersection weight of a variant is the the amount of named packages in the fam requires that appear in the
          variant regardless of the order

        @return a list with the intersecting weighted variants_slices sorted
        """
        intersection_weight_dict = self._weight_variants_against_family_request()

        ordered_variants = []
        for weight in sorted(intersection_weight_dict.keys()):  # Sorted, so we start adding the least weight first
            variants_slice = intersection_weight_dict[weight]
            variants_sorted_by_version_range = self._sort_variants_by_version_range(variants_slice,
                                                                                    self.fam_requires[:])
            ordered_variants.extend(variants_sorted_by_version_range)

        return ordered_variants

    def _weight_variants_against_family_request(self):
        """
        Group the variants of the same weight
        The weight to each variant is given by the intersection of its family names with the fam_requires

        @return a dict with weight as keys containing variants with the same intersection weight
        """
        fam_requires_set = set(self.fam_requires)
        weighted_dict = {}
        for variant in self.variants:
            weight = len(self._intersect_variant_with_package_request(fam_requires_set, variant))
            weighted_dict.setdefault(weight, []).append(variant)

        #TODO  to be correct a this point we should check every request in every variant to check if it contains
        # an antipackage (conflict) and give it negative weight, but it might be costly given it is not a common case?
        # Given that it is not a common case to have an anitpackage in the variants, and the fact that the
        # The antipackage will end up with the least priority when we sort its group we might be ok not sorting it here

        return weighted_dict

    def _intersect_variant_with_package_request(self, fam_requires_set, variant):
        """
        Calculates the intersection of a variant and the fam_requires
        """
        fams = extract_family_name_from_requirements(variant)
        intersection_set = set(fams) & fam_requires_set
        return intersection_set

    def _sort_variants_by_version_range(self, variants_slice, fam_requires):
        """
        Recursively start sorting the slice by VersionRange using the entries in the fam_requires
            If the sort is ambiguous keep sorting using the next entry in the fam_requires

                If we exhaust all the fam_requires and we still have ambiguous variants,
                pick the one that pulls the least number of packages.

                    If still ambiguous find the average positional weight of the fams not in the fam_requires and sort
                       by the VersionRange of the next highest weighted fam

        @param variants_slice: a slice of the original variants list
        @param fam_requires: a list with families (packages names)
        @return the variant_slice sorted by VersionRange.
        """

        ordered_variant_list = []

        if fam_requires:
            fam_name = fam_requires.pop(0)
            groups = self.groups_by_version_ranges(fam_name, variants_slice)
        else:
            # We could not break the tie by the fam_requires. Try with the weight by number of packages
            fam_name = None
            groups = self.group_by_number_of_packages(variants_slice)

        for _, tied_variants in sorted(groups.items(), key=itemgetter(0)):
            if len(tied_variants) == 1:
                # we broke the tie append
                ordered_variant_list.append(tied_variants[0])
            else:
                if not fam_name:
                    # If we were not able to break the tie based on the farm_requires, nor with by the number of
                    # packages in the tied variants, we get a list of families by average positional weight
                    # as the new key to sort by VersionRange
                    fam_requires = self._get_list_of_key_by_positional_weight(variants_slice)

                ordered_variant_list.extend(self._sort_variants_by_version_range(tied_variants, fam_requires[:]))

        return ordered_variant_list

    def groups_by_version_ranges(self, fam_name, variants_slice):
        """
        Groups the variant slice by VersionRange of a given fam_name

        @param fam_name: a string with a package name
        @param variants_slice: a list of variants
        @return: a dict with VersionRanges as keys containing a list of variants with the same VersionRange
        """
        group_dict = {}
        for variant in variants_slice:
            version_range = self._get_version_range_of_request_on_variant(fam_name, variant)
            group_dict.setdefault(version_range, []).append(variant)

        return group_dict



    def _get_version_range_of_request_on_variant(self, fam_name, variant):
        """
        Extracts the fam_name version range from the a variant

        @param fam_name: a string with a package name
        @param variant: a variant containing package requirements
        @return: a VersionRange - The version range of the package if it exists, the exact VersionRange if the package
        is a conflict, or the 'any VersionRange' if the the family is not found in the variant
        """
        matching_fam_names_in_variant = [req for req in variant if req.name == fam_name]
        if matching_fam_names_in_variant:
            # Get the highest version if thre is more than one matching name
            requirement = sorted(matching_fam_names_in_variant).pop()
            if not requirement.conflict:
                return requirement.range
            else:
                # This stack on top of VersionRange("") when sorted
                # TODO any other more meaningful VersionRange we know is going to be on top when we sort by range?
                return VersionRange("==")
        else:
            return VersionRange("")



    def group_by_number_of_packages(self, variants_slice):
        """
        Group the variants of the same weight
        More weight is given to the variant with the least amount of packages

        @param variants_slice: a list of variants
        @return: a dict with weight as keys containing a list of variants with the same length weight
        """
        group_dict = {}

        # find out the longest variant length
        max_length = max(len(v) for v in variants_slice)

        for variant in variants_slice:
            group_dict.setdefault(max_length - len(variant), []).append(variant)
        return group_dict


    def _get_list_of_key_by_positional_weight(self, variants_slice):
        """
        Gets the positional averaged weight of the variants that do not appear in the fam_requires

        weight=1 is given if the fam appears in index 0, weight=1/2 if appears in index 1, weight=1/3
         if appears in index 2, and so on


        @param variants_slice: a list of variants
        @return: an ordered list of family names by averaged positional weight
        """
        remaining_families_sorted_by_positional_weight = []
        averaged_weight_map = {}
        for variant in variants_slice:
            for w, req in enumerate(variant, start=1):
                if req.name not in self.fam_requires:
                    averaged_weight_map.setdefault(req.name, 0.0)
                    averaged_weight_map[req.name] += 1.0/w

        # sort by alphabetically first in case of tied weight
        sorted_alphabetically = sorted(averaged_weight_map.items(), key=lambda x: x[0].lower())
        # Now sorted by weight reversed, highest weight first
        sorted_by_weight = sorted(sorted_alphabetically, key=lambda x: x[1], reverse=True)

        remaining_families_sorted_by_positional_weight = [fam for fam, _ in sorted_by_weight]

        return remaining_families_sorted_by_positional_weight


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
    """A sorted list of package variants, loaded lazily."""
    def __init__(self, package_name, package_paths=None, package_requests=None, timestamp=0,
                 building=False, package_load_callback=None):
        self.package_name = package_name
        self.package_paths = package_paths
        self.package_requests = package_requests
        self.timestamp = timestamp
        self.building = building
        self.package_load_callback = package_load_callback
        self.variants = []

        it = iter_packages(self.package_name, paths=self.package_paths)
        self.packages = sorted(it, key=lambda x: x.version)
        if not self.packages:
            raise PackageFamilyNotFoundError("package family not found: %s"
                                             % package_name)

    def get_intersection(self, range, max_packages=0):
        """Get a list of variants that intersect with the given range.

        Args:
            range (`VersionRange`): Package version range.
            max_packages (int): Load only the first N packages found, ignored
                if zero.

        Returns:
            Two-tuple:
            - List of `PackageVariant` objects, in descending version order;
            - bool indicating whether there are packages still to be loaded. If
                True, more packages could be loaded, if False then all packages
                are loaded. This value can only be True when max_packages is
                non-zero.
        """
        num_packages = 0
        is_partial = False
        if self.packages:
            loaded_variants = []
            indexes = []

            for i, pkg in enumerate(self.packages):
                # checking version against range before timestamp is important
                # - metadata needs to be loaded to determine package timestamp.
                if pkg.version not in range:
                    continue

                if max_packages and (num_packages >= max_packages):
                    is_partial = True
                    break

                if not isinstance(pkg, list):
                    if self.package_load_callback:
                        self.package_load_callback(pkg)

                if self.timestamp and pkg.timestamp > self.timestamp:
                    continue

                # Remove the current package from the package_requests ..since it can not appear in its variants.
                # probably no much gain and we are creating a new list.. might remove this line?
                package_requests = [r for r in self.package_requests if r.name != pkg.name]

                indexes.append(i)
                variants_to_sort = []
                original_variants = []
                for var in pkg.iter_variants():
                    requires = var.get_requires(
                        build_requires=self.building)
                    variants_to_sort.append(requires)
                    original_variants.append(var)

                if any(variants_to_sort):
                    # timings.start("solver.sort_variants")
                    sorted_variants = VariantSorter(variants_to_sort, package_requests).sort_variants()
                    # timings.end("solver.sort_variants")
                else:
                    sorted_variants = variants_to_sort

                for var in original_variants:
                    # Map the variants to the new indexes in the sorted_variants
                    original_requires = var.get_requires(build_requires=self.building)
                    userdata = var.handle.to_dict()
                    new_index = var.index
                    if new_index is not None:
                        new_index = sorted_variants.index(original_requires)

                    variant = PackageVariant(name=self.package_name,
                                             version=var.version,
                                             requires=original_requires,
                                             index=new_index,
                                             userdata=userdata)
                    loaded_variants.append(variant)
                # sort all now by version and variant
                loaded_variants = sorted(loaded_variants, key=lambda v: (v.version, v.index))

                num_packages += 1

            if loaded_variants:
                self.variants = list(merge(self.variants, loaded_variants))
                for i in reversed(indexes):
                    del self.packages[i]

        variants = []
        for variant in self.variants:
            if variant.version in range:
                variants.append(variant)

        return (variants or None), is_partial

    def dump(self):
        print self.package_name
        for version, variants in self.packages:
            print str(version)
            for variant in variants:
                print "    %s" % str(variant)

    def __str__(self):
        strs = []
        for _, variants in self.packages:
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
                red = Reduction(name=variant.name,
                                version=variant.version,
                                variant_index=variant.index,
                                dependency=req,
                                conflicting_request=package_request)
                reductions.append(red)
                self.pr("removed %s (dep(%s) <--!--> %s)"
                        % (red.reducee_str(),
                           str(red.dependency),
                           str(red.conflicting_request)))
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

            range = ranges[0].union(ranges[1:])
            common_req = Requirement.construct(fam, range)
            return (slice, common_req)
        else:
            return (self, None)

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
                    for j, variant in enumerate(other_variants):
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

            return (slice, next_slice)

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
    def __init__(self, package_paths=None, package_requests=None, timestamp=0, building=False,
                 package_load_callback=None):
        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)
        self.timestamp = timestamp
        self.building = building
        self.package_request = package_requests
        self.package_load_callback = package_load_callback
        self.variant_lists = {}  # {package-name: _PackageVariantList}

    def get_variant_slice(self, package_name, range, max_packages=0):
        """Get a list of variants from the cache.

        Args:
            package_name (str): Name of package.
            range (`VersionRange`): Package version range.
            max_packages (int): Load only the first N packages found, ignored
                if zero. The return object's `is_partial` method indicates
                whether more packages could have been loaded.

        Returns:
            Two-tuple containing:
            - `_PackageVariantSlice` object;
            - bool indicating whether there are packages still to be loaded. If
                True, more packages could be loaded, if False then all packages
                are loaded. This value can only be True when max_packages is
                non-zero.
        """
        variant_list = self.variant_lists.get(package_name)
        if variant_list is None:
            variant_list = _PackageVariantList(
                package_name,
                package_requests=self.package_request,
                package_paths=self.package_paths,
                timestamp=self.timestamp,
                building=self.building,
                package_load_callback=self.package_load_callback)
            self.variant_lists[package_name] = variant_list

        variants, is_partial = variant_list.get_intersection(range, max_packages)
        if not variants:
            return None, False

        slice_ = _PackageVariantSlice(package_name, variants=variants)
        return slice_, is_partial


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
            A (_PackageScope, [Reduction]) tuple, where the scope is a new
            scope copy with reductions applied, or self if there were no
            reductions, or None if the slice was completely reduced.
        """
        if not self.package_request.conflict:
            new_slice, reductions = self.variant_slice.reduce(package_request)

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
                self.pr("extracted %s from %s"
                        % (str(package_request), str(self)))
                return (scope, package_request)

        return (self, None)

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
    deps = dict((k, set(v)-set([k])) for k, v in access_.iteritems())
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
                nodes = [nodes[i+1]] + nodes[:i+1] + nodes[i+2:]
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
                phase.status = SolverStatus.solved if phase._is_solved() else SolverStatus.exhausted
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
                        self.pr("merged extractions: %s" % str(request_list))
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
                            self.pr("added %s" % str(scope))

                        m = len(new_reqs)
                        for i in range(n, n+m):
                            for j in range(n+m):
                                if i != j:
                                    pending_reducts.add((i, j))

                        for i in range(n):
                            for j in range(n, n+m):
                                pending_reducts.add((i, j))
                else:
                    break

            if not pending_reducts:
                break

            # iteratively reduce until no more reductions possible
            self.pr.subheader("REDUCING:")
            while pending_reducts:

                if not self.solver.optimised:
                    # check all variants for reduction regardless
                    pending_reducts = set()
                    for i in range(len(scopes)):
                        for j in range(len(scopes)):
                            if i != j:
                                pending_reducts.add((i, j))

                # the sort here gives reproducible results, since order of
                # reducts affects the result
                for i, j in sorted(pending_reducts):
                    new_scope, reductions = scopes[j].reduce(
                        scopes[i].package_request)
                    if new_scope is None:
                        failure_reason = TotalReduction(reductions)
                        return _create_phase(SolverStatus.failed)
                    elif new_scope is not scopes[j]:
                        scopes[j] = new_scope
                        for i in range(len(scopes)):
                            if i != j:
                                pending_reducts.add((j, i))

                    pending_reducts -= set([(i, j)])

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
                r = scope.split()
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
        edges = set()
        edge_types = {}
        src_nodes = set()
        dest_nodes = set()
        request_nodes = set()
        requires_nodes = set()
        solved_nodes = set()
        failure_nodes = set()
        scopes = dict((x.package_name, x) for x in self.scopes)

        def _add_edge(src, dest, type_=None):
            if src != dest:
                src_nodes.add(src)
                dest_nodes.add(dest)
                e = (src, dest)
                edges.add(e)
                if type_:
                    edge_types[e] = type_

        def _str_scope(scope):
            variant = scope._get_solved_variant()
            return str(variant) if variant \
                else "(REQUIRE)%s" % str(scope).replace('*', '')

        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                solved_nodes.add(str(variant))

        # create (initial request --> scope) edges
        for req in self.package_requests:
            scope_ = scopes.get(req.name)
            if scope_:
                prefix = "(REQUIRE)" if req.conflict else "(REQUEST)"
                req_str = "%s%s" % (prefix, str(req))
                request_nodes.add(req_str)
                _add_edge(req_str, _str_scope(scope_))

        # for solved scopes, create:
        # - (scope --> requirement) edge, and;
        # - (requirement -> scope) edge, if it exists.
        for scope in self.scopes:
            variant = scope._get_solved_variant()
            if variant:
                for req in variant.requires_list.requirements:
                    req_str = "(REQUIRE)%s" % str(req)
                    requires_nodes.add(req_str)
                    _add_edge(str(variant), req_str)

                    scope_ = scopes.get(req.name)
                    if scope_:
                        # this may be a conflict not yet found because an
                        # earlier conflict caused the solve to fail.
                        if not req.conflicts_with(scope_.package_request):
                            _add_edge(req_str, _str_scope(scope_))

        # in an unfinished solve, there may be outstanding extractions - they
        # are dependencies between scopes that are not yet solved. They need to
        # be in the graph, because they may be related to conflicts.
        for (src_fam, _), dest_req in self.extractions.iteritems():
            scope_src = scopes.get(src_fam)
            if scope_src:
                str_dest_req = "(REQUIRE)%s" % str(dest_req)
                requires_nodes.add(str_dest_req)
                _add_edge(_str_scope(scope_src), str_dest_req)

                scope_dest = scopes.get(dest_req.name)
                if scope_dest:
                    # this may be a conflict not yet found because an
                    # earlier conflict caused the solve to fail.
                    if not scope_dest.package_request.conflicts_with(dest_req):
                        str_dest = _str_scope(scope_dest)
                        _add_edge(str_dest_req, str_dest)

        # show conflicts that caused a failed solve, if any
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
                    failure_nodes.add(str_reduct)
                    failure_nodes.add(str_confl_scope)
            elif isinstance(fr, DependencyConflicts):
                for conflict in fr.conflicts:
                    scope = scopes.get(conflict.conflicting_request.name)
                    dep_str = "(REQUIRE)%s" % str(conflict.dependency)
                    failure_nodes.add(dep_str)

                    if scope:
                        scope_str = _str_scope(scope)
                        _add_edge(dep_str, scope_str, "conflicts")
                        failure_nodes.add(scope_str)
                    else:
                        req_str = "(REQUIRE)%s" \
                            % str(conflict.conflicting_request)
                        requires_nodes.add(req_str)
                        _add_edge(dep_str, req_str, "conflicts")
                        failure_nodes.add(req_str)
            elif isinstance(fr, Cycle):
                str_a = str(fr.packages[-1])
                str_b = str(fr.packages[0])
                failure_nodes.add(str_a)
                failure_nodes.add(str_b)
                _add_edge(str_a, str_b, "cycle_label")

                for i, stmt in enumerate(fr.packages[:-1]):
                    str_a = str(stmt)
                    str_b = str(fr.packages[i+1])
                    failure_nodes.add(str_a)
                    failure_nodes.add(str_b)
                    _add_edge(str_a, str_b, "cycle")

        node_color = "#F6F6F6"
        request_color = "#FFFFAA"
        solved_color = "#AAFFAA"
        node_fontsize = 10

        nodes = src_nodes | dest_nodes
        g = digraph()

        def _node_label(n):
            return n.replace("(REQUEST)", "").replace("(REQUIRE)", "")

        for n in nodes:
            attrs = [("label", _node_label(n)),
                     ("fontsize", node_fontsize)]
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
                    g.set_edge_label(e, "CONFLICT")
                    g.add_edge_attribute(e, ("style", "bold"))
                    g.add_edge_attribute(e, ("color", "red"))
                    g.add_edge_attribute(e, ("fontcolor", "red"))
                elif type_ == "cycle":
                    g.add_edge_attribute(e, ("style", "bold"))
                    g.add_edge_attribute(e, ("color", "red"))
                    g.add_edge_attribute(e, ("fontcolor", "red"))
                elif type_ == "cycle_label":
                    g.set_edge_label(e, "CYCLE")
                    g.add_edge_attribute(e, ("style", "bold"))
                    g.add_edge_attribute(e, ("color", "red"))
                    g.add_edge_attribute(e, ("fontcolor", "red"))

        # prune nodes not related to failure
        if failure_nodes:
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
                # We changed the index to help the solver pick the 'preferred' variant
                # At this point we should add it back for the original index
                # variant.index = variant.userdata.variables.get('index', None)
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
                 buf=None, package_load_callback=None, max_depth=0,
                 package_cache=None, prune_unfailed=True):
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
            max_depth (int): If non-zero, this value limits the number of packages
                that can be loaded for any given package name. This effectively
                trims the search space - only the highest N package versions are
                searched. See associated `is_partial` property.
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
        self.max_depth = max_depth
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
        self._is_partial = False
        self._init()



        if package_cache:
            self.package_cache = package_cache
        else:
            self.package_cache = PackageVariantCache(self.package_paths,
                                                      package_requests=package_requests,
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
    def is_partial(self):
        """Returns True if this solve is 'partial'.

        This means that more packages could have been loaded during the solve,
        but they were not, due to the value of `max_depth`.
        """
        return self._is_partial

    @property
    def resolved_packages(self):
        """Return a list of PackageVariant objects, or None if the resolve did
        not complete or was unsuccessful.
        """
        if (self.status != SolverStatus.solved):
            return None

        final_phase = self.phase_stack[-1]
        from pprint import pprint as pp
        pp(final_phase)
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
        slice, is_partial = self.package_cache.get_variant_slice(
            package_name=package_name,
            range=range,
            max_packages=self.max_depth)

        if slice is not None:
            slice.pr = self.pr
            self._is_partial |= is_partial

        end_time = time.time()
        self.load_time += (end_time - start_time)
        return slice


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
        return "{%d,%d}" % (depth, count)

    def __str__(self):
        return "%s %s %s" % (self.status,
                             self._depth_label(),
                             str(self.phase_stack[-1]))
