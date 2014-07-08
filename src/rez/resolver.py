from rez.solver import Solver, SolverStatus
from rez.config import config
from rez.vendor.enum import Enum


class ResolverStatus(Enum):
    pending = ("The resolve has not yet started.", )
    solved = ("The resolve has completed successfully.", )
    failed = ("The resolve is not possible.", )
    aborted = ("The resolve was stopped by the user (via callback).", )

    def __init__(self, description):
        self.description = description


class Resolver(object):
    """The package resolver.

    The Resolver uses a combination of Solver(s) and cache(s) to resolve a
    package request as quickly as possible.
    """
    def __init__(self, package_requests, package_paths=None, caching=True,
                 timestamp=0, callback=None, building=False, verbose=False):
        """Create a Resolver.

        Args:
            package_requests: List of Requirement objects representing the
                request.
            package_paths: List of paths to search for pkgs, defaults to
                config.packages_path.
            caching: If True, utilise cache(s) in order to speed up the
                resolve.
            callback: If not None, this callable will be called prior to each
                solve step. It is passed a single argument - a string showing
                the current solve state. If the return value of the callable is
                truthy, the solve continues, otherwise the solve is stopped.
            building: True if we're resolving for a build.
        """
        self.package_requests = package_requests
        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)
        self.caching = caching
        self.timestamp = timestamp
        self.callback = callback
        self.building = building
        self.verbose = verbose

        self.status_ = ResolverStatus.pending
        self.resolved_packages_ = None
        self.failure_description = None
        self.graph_ = None

        self.solve_time = 0.0  # time spent solving
        self.load_time = 0.0   # time spent loading package resources

    def solve(self):
        """Perform the solve."""
        solver = Solver(self.package_requests,
                        package_paths=self.package_paths,
                        timestamp=self.timestamp,
                        callback=self.callback,
                        building=self.building,
                        verbose=self.verbose)

        solver.solve()
        self._set_result(solver)

    @property
    def status(self):
        """Return the current status of the resolve.

        Returns one of:
            pending - the resolve has not yet started.
            solved - the resolve has completed successfully.
            failed - the resolve is not possible.
            aborted - the resolve was stopped by the user (via callback).
        """
        return self.status_

    @property
    def resolved_packages(self):
        """Return a list of PackageVariant objects, or None if the resolve did
        not complete or was unsuccessful.
        """
        return self.resolved_packages_

    @property
    def graph(self):
        """Return the resolve graph.

        The resolve graph shows unsuccessful as well as successful resolves.

        Returns:
            A pygraph.digraph object, or None if the solve has not completed.
        """
        return self.graph_

    def _set_result(self, solver):
        st = solver.status
        pkgs = None

        if st == SolverStatus.unsolved:
            self.status_ = ResolverStatus.aborted
            self.failure_description = "the resolve was aborted by the user"
        elif st == SolverStatus.failed:
            self.status_ = ResolverStatus.failed
            self.failure_description = solver.failure_reason().description()
        elif st == SolverStatus.solved:
            self.status_ = ResolverStatus.solved
            pkgs = solver.resolved_packages

        self.resolved_packages_ = pkgs
        self.graph_ = solver.get_graph()
        self.solve_time = solver.solve_time
        self.load_time = solver.load_time
