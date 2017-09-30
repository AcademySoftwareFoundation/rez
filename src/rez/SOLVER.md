# Description Of Solver Algorithm

## Overview

* A **phase** is a current state of the solve. It contains a list of **scopes**.
* A **scope** is a package request. If the request isn't a conflict, then a scope
  also contains the actual list of variants that match the request.

The solve loop performs 5 different types of operations:

* **EXTRACT**. This happens when a common dependency is found in all the variants
  in a scope. For example if every version of pkg 'foo' depends on some version
  of python, the 'extracted' dependency might be "python-2.6|2.7". An extraction
  then results in either an INTERSECT or an ADD.

* **INTERSECT**: This happens when an extracted dependency overlaps with an existing
  scope. For example "python-2" might be a current scope. Pkg foo's common dependency
  python-2.6|2.7 would be 'intersected' with this scope. This might result in a
  conflict, which would cause the whole phase to fail (and possibly the whole solve).
  Or, as in this case, it narrows an existing scope to 'python-2.6|2.7'.

* **ADD**: This happens when an extraction is a new pkg request. A new scope is
  created and added to the current list of scopes.

* **REDUCE**: This is when a scope iterates over all of its variants and removes those
  that conflict with another scope. If this removes all the variants in the scope,
  the phase has failed - this is called a "total reduction". This type of failure
  is not common - usually it's a conflicting INTERSECT that causes a failure.

* **SPLIT**: Once a phase has been extracted/intersected/added/reduced as much as
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

Following the process above, we maintain a 'phase stack'. We run a loop, and in
each loop, we attempt to solve the phase at the top of the stack. If the phase
becomes exhaused, then it is split, and replaced with 2 phases (so the stack
grows by 1). If the phase is solved, then we have the solution, and the other
phases are discarded. If the phase fails to solve, then it is removed from the
stack - if the stack is then empty, then there is no solution.

## Pseudocode

The pseudocode for a solve looks like this:

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

## Interpreting Debugging Output

Solver debugging is enabled using the *rez-env* *-v* flag. Repeat for more
vebosity, to a max of *-vvv*.

### Scope Syntax

Before describing all the sections of output during a solve, we need to explain
the scope syntax. This describes the state of a scope, and you'll see it a lot
in solver output.

* `[foo==1.2.0]` This is a scope containing exactly one variant. In this case it
  is a *null* variant (a package that has no variants).

* `[foo-1.2.0[1]]` This is a scope containing exactly one variant. This example
  shows the 1-index variant of the package foo-1.2.0

    [foo-1.2.0[0,1]]

This is a scope containing two variants from one package version.

    [foo-1.2.0..1.3.5(6)]

This is a scope containing 6 variants from 6 different package versions, where
the packages are all >= 1.2.0 and <= 1.3.5.





    request: foo-1.2 bah-3 ~foo-1

You will see this once, at the start of the solve. It simply prints the initial
request list.

    merged_request: foo-1.2 bah-3

You will see this once and immediately after the `request:` output. It shows a
simplified (merged) version of the initial request. Notice here how `~foo-1` is
gone - this is because the intersection of `foo-1.2` and `~foo-1` is simply
`foo-1.2`.

    pushed {0,0}: [foo==1.2.0[0,1]]* bah[3.0.5..3.4.0(6)]*



    --------------------------------------------------------------------------------
    SOLVE #1...
    --------------------------------------------------------------------------------

This output indicates that a phase is starting. The number indicates the number
of phases that have been solved so far (1-indexed), regardless of how many have
failed or succeeded:
