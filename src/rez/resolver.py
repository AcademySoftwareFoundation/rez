from rez.solver import Solver, SolverStatus, PackageVariantCache
from rez.package_repository import package_repository_manager
from rez.packages_ import get_variant, get_last_release_time
from rez.package_filter import PackageFilterList, TimestampRule
from rez.utils.memcached import memcached_client, pool_memcached_connections
from rez.utils.logging_ import log_duration
from rez.config import config
from rez.vendor.enum import Enum
from contextlib import contextmanager
from hashlib import sha1
import os


class ResolverStatus(Enum):
    """ Enum to represent the current state of a resolver instance.  The enum
    also includes a human readable description of what the state represents.
    """

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
    def __init__(self, context, package_requests, package_paths, package_filter=None,
                 package_orderers=None, timestamp=0, callback=None, building=False,
                 verbosity=False, buf=None, package_load_callback=None, caching=True,
                 suppress_passive=False, print_stats=False):
        """Create a Resolver.

        Args:
            package_requests: List of Requirement objects representing the
                request.
            package_paths: List of paths to search for pkgs.
            package_filter (`PackageFilterList`): Package filter.
            package_orderers (list of `PackageOrder`): Custom package ordering.
            callback: See `Solver`.
            package_load_callback: If not None, this callable will be called
                prior to each package being loaded. It is passed a single
                `Package` object.
            building: True if we're resolving for a build.
            caching: If True, cache(s) may be used to speed the resolve. If
                False, caches will not be used.
            print_stats (bool): If true, print advanced solver stats at the end.
        """
        self.context = context
        self.package_requests = package_requests
        self.package_paths = package_paths
        self.timestamp = timestamp
        self.callback = callback
        self.package_orderers = package_orderers
        self.package_load_callback = package_load_callback
        self.building = building
        self.verbosity = verbosity
        self.caching = caching
        self.buf = buf
        self.suppress_passive = suppress_passive
        self.print_stats = print_stats

        # store hash of package orderers. This is used in the memcached key
        if package_orderers:
            sha1s = ''.join(x.sha1 for x in package_orderers)
            self.package_orderers_hash = sha1(sha1s).hexdigest()
        else:
            self.package_orderers_hash = ''

        # store hash of pre-timestamp-combined package filter. This is used in
        # the memcached key
        if package_filter:
            self.package_filter_hash = package_filter.sha1
        else:
            self.package_filter_hash = ''

        # combine timestamp and package filter into single filter
        if self.timestamp:
            if package_filter:
                self.package_filter = package_filter.copy()
            else:
                self.package_filter = PackageFilterList()
            rule = TimestampRule.after(self.timestamp)
            self.package_filter.add_exclusion(rule)
        else:
            self.package_filter = package_filter

        self.status_ = ResolverStatus.pending
        self.resolved_packages_ = None
        self.failure_description = None
        self.graph_ = None
        self.from_cache = False
        self.memcached_servers = config.memcached_uri if config.resolve_caching else None

        self.solve_time = 0.0  # time spent solving
        self.load_time = 0.0   # time spent loading package resources

        self._print = config.debug_printer("resolve_memcache")

    @pool_memcached_connections
    def solve(self):
        """Perform the solve.
        """
        with log_duration(self._print, "memcache get (resolve) took %s"):
            solver_dict = self._get_cached_solve()

        if solver_dict:
            self.from_cache = True
            self._set_result(solver_dict)
        else:
            self.from_cache = False
            solver = self._solve()
            solver_dict = self._solver_to_dict(solver)
            self._set_result(solver_dict)

            with log_duration(self._print, "memcache set (resolve) took %s"):
                self._set_cached_solve(solver_dict)

    @property
    def status(self):
        """Return the current status of the resolve.

        Returns:
          ResolverStatus.
        """
        return self.status_

    @property
    def resolved_packages(self):
        """Get the list of resolved packages.

        Returns:
            List of `PackageVariant` objects, or None if the resolve has not
            completed.
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

    def _get_variant(self, variant_handle):
        return get_variant(variant_handle, context=self.context)

    def _get_cached_solve(self):
        """Find a memcached resolve.

        If there is NOT a resolve timestamp:
            - fetch a non-timestamped memcache entry;
            - if no entry, then fail;
            - if packages have changed, then:
              - delete the entry;
              -  fail;
            - if no packages in the entry have been released since, then
              - use the entry and return;
            - else:
              - delete the entry;
              - fail.

        If there IS a resolve timestamp (let us call this T):
            - fetch a non-timestamped memcache entry;
            - if entry then:
              - if no packages have changed, then:
                - if no packages in the entry have been released since:
                  - if no packages in the entry were released after T, then
                    - use the entry and return;
                - else:
                  - delete the entry;
              - else:
                - delete the entry;
            - fetch a timestamped (T) memcache entry;
            - if no entry, then fail;
            - if packages have changed, then:
              - delete the entry;
              - fail;
            - else:
              - use the entry.

        This behaviour exists specifically so that resolves that use a
        timestamp but set that to the current time, can be reused by other
        resolves if nothing has changed. Older resolves however, can only be
        reused if the timestamp matches exactly (but this might happen a lot -
        consider a workflow where a work area is tied down to a particular
        timestamp in order to 'lock' it from any further software releases).
        """
        if not (self.caching and self.memcached_servers):
            return None

        # these caches avoids some potentially repeated file stats
        variant_states = {}
        last_release_times = {}

        def _hit(data):
            solver_dict, _, _ = data
            return solver_dict

        def _miss():
            self._print("No cache key retrieved")
            return None

        def _delete_cache_entry(key):
            with self._memcached_client() as client:
                client.delete(key)
            self._print("Discarded entry: %r", key)

        def _retrieve(timestamped):
            key = self._memcache_key(timestamped=timestamped)
            self._print("Retrieving memcache key: %r", key)
            with self._memcached_client() as client:
                data = client.get(key)
            return key, data

        def _packages_changed(key, data):
            solver_dict, _, variant_states_dict = data
            for variant_handle in solver_dict.get("variant_handles", []):
                variant = self._get_variant(variant_handle)
                old_state = variant_states_dict.get(variant.name)

                new_state = variant_states.get(variant)
                if new_state is None:
                    try:
                        repo = variant.resource._repository
                        new_state = repo.get_variant_state_handle(variant.resource)
                    except (IOError, OSError) as e:
                        # if, ie a package file was deleted on disk, then
                        # an IOError or OSError will be raised when we try to
                        # read from it - assume that the packages have changed!
                        self._print("Error loading %r (assuming cached state "
                                    "changed): %s", variant.qualified_name,
                                    e)
                        return True
                    variant_states[variant] = new_state

                if old_state != new_state:
                    self._print("%r has been modified", variant.qualified_name)
                    return True
            return False

        def _releases_since_solve(key, data):
            _, release_times_dict, _ = data
            for package_name, release_time in release_times_dict.items():
                time_ = last_release_times.get(package_name)
                if time_ is None:
                    time_ = get_last_release_time(package_name, self.package_paths)
                    last_release_times[package_name] = time_

                if time_ != release_time:
                    self._print(
                        "A newer version of %r (%d) has been released since the "
                        "resolve was cached (latest release in cache was %d) "
                        "(entry: %r)", package_name, time_, release_time, key)
                    return True
            return False

        def _timestamp_is_earlier(key, data):
            _, release_times_dict, _ = data
            for package_name, release_time in release_times_dict.items():
                if self.timestamp < release_time:
                    self._print("Resolve timestamp (%d) is earlier than %r in "
                                "solve (%d) (entry: %r)", self.timestamp,
                                package_name, release_time, key)
                    return True
            return False

        key, data = _retrieve(False)

        if self.timestamp:
            if data:
                if _packages_changed(key, data) or _releases_since_solve(key, data):
                    _delete_cache_entry(key)
                elif not _timestamp_is_earlier(key, data):
                    return _hit(data)

            key, data = _retrieve(True)
            if not data:
                return _miss()
            if _packages_changed(key, data):
                _delete_cache_entry(key)
                return _miss()
            else:
                return _hit(data)
        else:
            if not data:
                return _miss()
            if _packages_changed(key, data) or _releases_since_solve(key, data):
                _delete_cache_entry(key)
                return _miss()
            else:
                return _hit(data)

    @contextmanager
    def _memcached_client(self):
        with memcached_client(self.memcached_servers,
                              debug=config.debug_memcache) as client:
            yield client

    def _set_cached_solve(self, solver_dict):
        """Store a solve to memcached.

        If there is NOT a resolve timestamp:
            - store the solve to a non-timestamped entry.

        If there IS a resolve timestamp (let us call this T):
            - if NO newer package in the solve has been released since T,
              - then store the solve to a non-timestamped entry;
            - else:
              - store the solve to a timestamped entry.
        """
        if self.status_ != ResolverStatus.solved:
            return  # don't cache failed solves

        if not (self.caching and self.memcached_servers):
            return

        # most recent release times get stored with solve result in the cache
        releases_since_solve = False
        release_times_dict = {}
        variant_states_dict = {}

        for variant in self.resolved_packages_:
            time_ = get_last_release_time(variant.name, self.package_paths)

            # don't cache if a release time isn't known
            if time_ == 0:
                self._print("Did not send memcache key: a repository could "
                            "not provide a most recent release time for %r",
                            variant.name)
                return

            if self.timestamp and self.timestamp < time_:
                releases_since_solve = True

            release_times_dict[variant.name] = time_
            repo = variant.resource._repository
            variant_states_dict[variant.name] = \
                repo.get_variant_state_handle(variant.resource)

        timestamped = (self.timestamp and releases_since_solve)
        key = self._memcache_key(timestamped=timestamped)
        data = (solver_dict, release_times_dict, variant_states_dict)
        with self._memcached_client() as client:
            client.set(key, data)
        self._print("Sent memcache key: %r", key)

    def _memcache_key(self, timestamped=False):
        """Makes a key suitable as a memcache entry."""
        request = tuple(map(str, self.package_requests))
        repo_ids = []
        for path in self.package_paths:
            repo = package_repository_manager.get_repository(path)
            repo_ids.append(repo.uid)

        t = ["resolve",
             request,
             tuple(repo_ids),
             self.package_filter_hash,
             self.package_orderers_hash,
             self.building,
             config.prune_failed_graph]

        if timestamped and self.timestamp:
            t.append(self.timestamp)

        return str(tuple(t))

    def _solve(self):
        solver = Solver(package_requests=self.package_requests,
                        package_paths=self.package_paths,
                        context=self.context,
                        package_filter=self.package_filter,
                        package_orderers=self.package_orderers,
                        callback=self.callback,
                        package_load_callback=self.package_load_callback,
                        building=self.building,
                        verbosity=self.verbosity,
                        prune_unfailed=config.prune_failed_graph,
                        buf=self.buf,
                        suppress_passive=self.suppress_passive,
                        print_stats=self.print_stats)
        solver.solve()

        return solver

    def _set_result(self, solver_dict):
        self.status_ = solver_dict.get("status")
        self.graph_ = solver_dict.get("graph")
        self.solve_time = solver_dict.get("solve_time")
        self.load_time = solver_dict.get("load_time")
        self.failure_description = solver_dict.get("failure_description")

        self.resolved_packages_ = None
        if self.status_ == ResolverStatus.solved:
            # convert solver.Variants to packages.Variants
            self.resolved_packages_ = []
            for variant_handle in solver_dict.get("variant_handles", []):
                variant = self._get_variant(variant_handle)
                self.resolved_packages_.append(variant)

    @classmethod
    def _solver_to_dict(cls, solver):
        graph_ = solver.get_graph()
        solve_time = solver.solve_time
        load_time = solver.load_time
        failure_description = None
        variant_handles = None

        st = solver.status
        if st == SolverStatus.unsolved:
            status_ = ResolverStatus.aborted
            failure_description = solver.abort_reason
        elif st == SolverStatus.failed:
            status_ = ResolverStatus.failed
            failure_description = solver.failure_description()
        elif st == SolverStatus.solved:
            status_ = ResolverStatus.solved

            variant_handles = []
            for solver_variant in solver.resolved_packages:
                variant_handle_dict = solver_variant.handle
                variant_handles.append(variant_handle_dict)

        return dict(
            status=status_,
            graph=graph_,
            solve_time=solve_time,
            load_time=load_time,
            failure_description=failure_description,
            variant_handles=variant_handles)


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
