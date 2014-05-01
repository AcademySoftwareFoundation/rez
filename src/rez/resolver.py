from rez.solver import Solver
from rez.settings import settings



class Resolver(object):
    """The package resolver.

    The Resolver uses a combination of Solver(s) and cache(s) to resolve a
    package request as quickly as possible.
    """
    def __init__(self, package_requests, package_paths=None,
                 use_cache=True, callback=None, verbose=True):
        """Create a Resolver.

        Args:
            package_requests: List of Requirement objects representing the request.
            package_paths: List of paths to search for pkgs, defaults to
                settings.packages_path.
            use_cache: If True, utilise cache(s) in order to speed up the resolve.
            callback: If not None, this callable will be called prior to each
                solve step. It is passed a single argument - a string showing the
                current solve state. If the return value of the callable is
                truthy, the solve continues, otherwise the solve is stopped.
        """
        self.package_requests = package_requests
        self.package_paths = package_paths or settings.packages_path
        self.use_cache = use_cache
        self.callback = callback
        self.verbose = verbose

        self.status_ = "pending"
        self.resolved_packages_ = None
        self.graph_ = None

    def solve(self):
        """Perform the solve."""
        solver = Solver(self.package_requests,
                        package_paths=self.package_paths,
                        callback=self.callback,
                        verbose=self.verbose)

        solver.solve()
        self._set_result(solver)


    @property
    def status(self):
        """Return the current status of the resolve. One of:
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

        if st == "unsolved":
            st = "aborted"
        elif st == "solved":
            pkgs = solver.resolved_packages

        self.status_ = st
        self.resolved_packages_ = pkgs
        self.graph_ = solver.get_graph()
