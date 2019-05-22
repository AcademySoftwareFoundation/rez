from __future__ import print_function
from rez.vendor.six import six
from rez import __version__, module_root_path
from rez.package_repository import package_repository_manager
from rez.solver import SolverCallbackReturn
from rez.resolver import Resolver, ResolverStatus
from rez.system import system
from rez.config import config
from rez.util import shlex_join, dedup
from rez.utils.sourcecode import SourceCodeError
from rez.utils.colorize import critical, heading, local, implicit, Printer
from rez.utils.formatting import columnise, PackageRequest, ENV_VAR_REGEX
from rez.utils.data_utils import deep_del
from rez.utils.filesystem import TempDirs
from rez.utils.memcached import pool_memcached_connections
from rez.backport.shutilwhich import which
from rez.rex import RexExecutor, Python, OutputStyle
from rez.rex_bindings import VersionBinding, VariantBinding, \
    VariantsBinding, RequirementsBinding
from rez import package_order
from rez.packages_ import get_variant, iter_packages
from rez.package_filter import PackageFilterList
from rez.shells import create_shell
from rez.exceptions import ResolvedContextError, PackageCommandError, RezError
from rez.utils.graph_utils import write_dot, write_compacted, read_graph_from_string
from rez.vendor.version.version import VersionRange
from rez.vendor.enum import Enum
from rez.vendor import yaml
from rez.utils import json
from rez.utils.yaml import dump_yaml

from tempfile import mkdtemp
from functools import wraps
import getpass
import socket
import threading
import traceback
import inspect
import time
import sys
import os
import os.path


class RezToolsVisibility(Enum):
    """Determines if/how rez cli tools are added back to PATH within a
    resolved environment."""
    never = 0               # Don't expose rez in resolved env
    append = 1              # Append to PATH in resolved env
    prepend = 2             # Prepend to PATH in resolved env


class SuiteVisibility(Enum):
    """Defines what suites on $PATH stay visible when a new rez environment is
    resolved."""
    never = 0               # Don't attempt to keep any suites visible in a new env
    always = 1              # Keep suites visible in any new env
    parent = 2              # Keep only the parent suite of a tool visible
    parent_priority = 3     # Keep all suites visible and the parent takes precedence


class PatchLock(Enum):
    """ Enum to represent the 'lock type' used when patching context objects.
    """
    no_lock = ("No locking", -1)
    lock_2 = ("Minor version updates only (X.*)", 1)
    lock_3 = ("Patch version updates only (X.X.*)", 2)
    lock_4 = ("Build version updates only (X.X.X.*)", 3)
    lock = ("Exact version", -1)

    __order__ = "no_lock,lock_2,lock_3,lock_4,lock"

    def __init__(self, description, rank):
        self.description = description
        self.rank = rank


def get_lock_request(name, version, patch_lock, weak=True):
    """Given a package and patch lock, return the equivalent request.

    For example, for object 'foo-1.2.1' and lock type 'lock_3', the equivalent
    request is '~foo-1.2'. This restricts updates to foo to patch-or-lower
    version changes only.

    For objects not versioned down to a given lock level, the closest possible
    lock is applied. So 'lock_3' applied to 'foo-1' would give '~foo-1'.

    Args:
        name (str): Package name.
        version (Version): Package version.
        patch_lock (PatchLock): Lock type to apply.

    Returns:
        `PackageRequest` object, or None if there is no equivalent request.
    """
    ch = '~' if weak else ''
    if patch_lock == PatchLock.lock:
        s = "%s%s==%s" % (ch, name, str(version))
        return PackageRequest(s)
    elif (patch_lock == PatchLock.no_lock) or (not version):
        return None
    version_ = version.trim(patch_lock.rank)
    s = "%s%s-%s" % (ch, name, str(version_))
    return PackageRequest(s)


class ResolvedContext(object):
    """A class that resolves, stores and spawns Rez environments.

    The main Rez entry point for creating, saving, loading and executing
    resolved environments. A ResolvedContext object can be saved to file and
    loaded at a later date, and it can reconstruct the equivalent environment
    at that time. It can spawn interactive and non-interactive shells, in any
    supported shell plugin type, such as bash and tcsh. It can also run a
    command within a configured python namespace, without spawning a child
    shell.
    """
    serialize_version = (4, 3)
    tmpdir_manager = TempDirs(config.context_tmpdir, prefix="rez_context_")

    context_tracking_payload = None
    context_tracking_lock = threading.Lock()

    class Callback(object):
        def __init__(self, max_fails, time_limit, callback, buf=None):
            self.max_fails = max_fails
            self.time_limit = time_limit
            self.callback = callback
            self.start_time = time.time()
            self.buf = buf or sys.stdout

        def __call__(self, state):
            if self.max_fails != -1 and state.num_fails >= self.max_fails:
                reason = ("fail limit reached: aborted after %d failures"
                          % state.num_fails)
                return SolverCallbackReturn.fail, reason
            if self.time_limit != -1:
                secs = time.time() - self.start_time
                if secs > self.time_limit:
                    return SolverCallbackReturn.abort, "time limit exceeded"
            if self.callback:
                return self.callback(state)
            return SolverCallbackReturn.keep_going, ''

    def __init__(self, package_requests, verbosity=0, timestamp=None,
                 building=False, caching=None, package_paths=None,
                 package_filter=None, package_orderers=None, max_fails=-1,
                 add_implicit_packages=True, time_limit=-1, callback=None,
                 package_load_callback=None, buf=None, suppress_passive=False,
                 print_stats=False):
        """Perform a package resolve, and store the result.

        Args:
            package_requests: List of strings or PackageRequest objects
                representing the request.
            verbosity: Verbosity level. One of [0,1,2].
            timestamp: Ignore packages released after this epoch time. Packages
                released at exactly this time will not be ignored.
            building: True if we're resolving for a build.
            caching: If True, cache(s) may be used to speed the resolve. If
                False, caches will not be used. If None, config.resolve_caching
                is used.
            package_paths: List of paths to search for pkgs, defaults to
                config.packages_path.
            package_filter (`PackageFilterBase`): Filter used to exclude certain
                packages. Defaults to settings from config.package_filter. Use
                `package_filter.no_filter` to remove all filtering.
            package_orderers (list of `PackageOrder`): Custom package ordering.
            add_implicit_packages: If True, the implicit package list defined
                by config.implicit_packages is appended to the request.
            max_fails (int): Abort the resolve if the number of failed steps is
                greater or equal to this number. If -1, does not abort.
            time_limit (int): Abort the resolve if it takes longer than this
                many seconds. If -1, there is no time limit.
            callback: See `Solver`.
            package_load_callback: If not None, this callable will be called
                prior to each package being loaded. It is passed a single
                `Package` object.
            buf (file-like object): Where to print verbose output to, defaults
                to stdout.
            suppress_passive (bool): If True, don't print debugging info that
                has had no effect on the solve. This argument only has an
                effect if `verbosity` > 2.
            print_stats (bool): If true, print advanced solver stats at the end.
        """
        self.load_path = None

        # resolving settings
        self.requested_timestamp = timestamp
        self.timestamp = self.requested_timestamp or int(time.time())
        self.building = building
        self.implicit_packages = []
        self.caching = config.resolve_caching if caching is None else caching
        self.verbosity = verbosity

        self._package_requests = []
        for req in package_requests:
            if isinstance(req, six.string_types):
                req = PackageRequest(req)
            self._package_requests.append(req)

        if add_implicit_packages:
            self.implicit_packages = [PackageRequest(x)
                                      for x in config.implicit_packages]

        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)
        self.package_paths = list(dedup(self.package_paths))

        self.package_filter = (PackageFilterList.singleton if package_filter is None
                               else package_filter)

        self.package_orderers = package_orderers

        # patch settings
        self.default_patch_lock = PatchLock.no_lock
        self.patch_locks = {}

        # info about env the resolve occurred in
        self.rez_version = __version__
        self.rez_path = module_root_path
        self.user = getpass.getuser()
        self.host = system.hostname
        self.platform = system.platform
        self.arch = system.arch
        self.os = system.os
        self.created = int(time.time())

        # resolve results
        self.status_ = ResolverStatus.pending
        self._resolved_packages = None
        self.failure_description = None
        self.graph_string = None
        self.graph_ = None
        self.from_cache = None

        # stats
        self.solve_time = 0.0  # total solve time, inclusive of load time
        self.load_time = 0.0  # total time loading packages (disk or memcache)
        self.num_loaded_packages = 0  # num packages loaded (disk or memcache)

        # the pre-resolve bindings. We store these because @late package.py
        # functions need them, and we cache them to avoid cost
        self.pre_resolve_bindings = None

        # suite information
        self.parent_suite_path = None
        self.suite_context_name = None

        # perform the solve
        callback_ = self.Callback(buf=buf,
                                  max_fails=max_fails,
                                  time_limit=time_limit,
                                  callback=callback)

        def _package_load_callback(package):
            if package_load_callback:
                package_load_callback(package)
            self.num_loaded_packages += 1

        request = self.requested_packages(include_implicit=True)

        resolver = Resolver(context=self,
                            package_requests=request,
                            package_paths=self.package_paths,
                            package_filter=self.package_filter,
                            package_orderers=self.package_orderers,
                            timestamp=self.requested_timestamp,
                            building=self.building,
                            caching=self.caching,
                            callback=callback_,
                            package_load_callback=_package_load_callback,
                            verbosity=verbosity,
                            buf=buf,
                            suppress_passive=suppress_passive,
                            print_stats=print_stats)

        resolver.solve()

        # convert the results
        self.status_ = resolver.status
        self.solve_time = resolver.solve_time
        self.load_time = resolver.load_time
        self.failure_description = resolver.failure_description
        self.graph_ = resolver.graph
        self.from_cache = resolver.from_cache

        if self.status_ == ResolverStatus.solved:
            self._resolved_packages = []

            for variant in resolver.resolved_packages:
                variant.set_context(self)
                self._resolved_packages.append(variant)

        # track context usage
        if config.context_tracking_host:
            data = self.to_dict(fields=config.context_tracking_context_fields)
            self._track_context(data, action="created")

    def __str__(self):
        request = self.requested_packages(include_implicit=True)
        req_str = " ".join(str(x) for x in request)
        if self.status == ResolverStatus.solved:
            res_str = " ".join(x.qualified_name for x in self._resolved_packages)
            return "%s(%s ==> %s)" % (self.status.name, req_str, res_str)
        else:
            return "%s:%s(%s)" % (self.__class__.__name__,
                                  self.status.name, req_str)

    @property
    def success(self):
        """True if the context has been solved, False otherwise."""
        return (self.status_ == ResolverStatus.solved)

    @property
    def status(self):
        """Return the current status of the context.

        Returns:
            ResolverStatus.
        """
        return self.status_

    def requested_packages(self, include_implicit=False):
        """Get packages in the request.

        Args:
            include_implicit (bool): If True, implicit packages are appended
                to the result.

        Returns:
            List of `PackageRequest` objects.
        """
        if include_implicit:
            return self._package_requests + self.implicit_packages
        else:
            return self._package_requests

    @property
    def resolved_packages(self):
        """Get packages in the resolve.

        Returns:
            List of `Variant` objects, or None if the resolve failed.
        """
        return self._resolved_packages

    def set_load_path(self, path):
        """Set the path that this context was reportedly loaded from.

        You may want to use this method in cases where a context is saved to
        disk, but you need to associate this new path with the context while it
        is still in use.
        """
        self.load_path = path

    def __eq__(self, other):
        """Equality test.

        Two contexts are considered equal if they have a equivalent request,
        and an equivalent resolve. Other details, such as timestamp, are not
        considered.
        """
        return (isinstance(other, ResolvedContext)
                and other.requested_packages(True) == self.requested_packages(True)
                and other.resolved_packages == self.resolved_packages)

    def __hash__(self):
        list_ = []
        req = self.requested_packages(True)
        list_.append(tuple(req))
        res = self.resolved_packages
        if res is None:
            list_.append(None)
        else:
            list_.append(tuple(res))

        value = tuple(list_)
        return hash(value)

    @property
    def has_graph(self):
        """Return True if the resolve has a graph."""
        return bool((self.graph_ is not None) or self.graph_string)

    def get_resolved_package(self, name):
        """Returns a `Variant` object or None if the package is not in the
        resolve.
        """
        pkgs = [x for x in self._resolved_packages if x.name == name]
        return pkgs[0] if pkgs else None

    def copy(self):
        """Returns a shallow copy of the context."""
        import copy
        return copy.copy(self)

    # TODO: deprecate in favor of patch() method
    def get_patched_request(self, package_requests=None,
                            package_subtractions=None, strict=False, rank=0):
        """Get a 'patched' request.

        A patched request is a copy of this context's request, but with some
        changes applied. This can then be used to create a new, 'patched'
        context.

        New package requests override original requests based on the type -
        normal, conflict or weak. So 'foo-2' overrides 'foo-1', '!foo-2'
        overrides '!foo-1' and '~foo-2' overrides '~foo-1', but a request such
        as '!foo-2' would not replace 'foo-1' - it would be added instead.

        Note that requests in `package_requests` can have the form '^foo'. This
        is another way of supplying package subtractions.

        Any new requests that don't override original requests are appended,
        in the order that they appear in `package_requests`.

        Args:
            package_requests (list of str or list of `PackageRequest`):
                Overriding requests.
            package_subtractions (list of str): Any original request with a
                package name in this list is removed, before the new requests
                are added.
            strict (bool): If True, the current context's resolve is used as the
                original request list, rather than the request.
            rank (int): If > 1, package versions can only increase in this rank
                and further - for example, rank=3 means that only version patch
                numbers are allowed to increase, major and minor versions will
                not change. This is only applied to packages that have not been
                explicitly overridden in `package_requests`. If rank <= 1, or
                `strict` is True, rank is ignored.

        Returns:
            List of `PackageRequest` objects that can be used to construct a
            new `ResolvedContext` object.
        """
        # assemble source request
        if strict:
            request = []
            for variant in self.resolved_packages:
                req = PackageRequest(variant.qualified_package_name)
                request.append(req)
        else:
            request = self.requested_packages()[:]

        # convert '^foo'-style requests to subtractions
        if package_requests:
            package_subtractions = package_subtractions or []
            indexes = []
            for i, req in enumerate(package_requests):
                name = str(req)
                if name.startswith('^'):
                    package_subtractions.append(name[1:])
                    indexes.append(i)
            for i in reversed(indexes):
                del package_requests[i]

        # apply subtractions
        if package_subtractions:
            request = [x for x in request if x.name not in package_subtractions]

        # apply overrides
        if package_requests:
            request_dict = dict((x.name, (i, x)) for i, x in enumerate(request))
            request_ = []

            for req in package_requests:
                if isinstance(req, six.string_types):
                    req = PackageRequest(req)

                if req.name in request_dict:
                    i, req_ = request_dict[req.name]
                    if (req_ is not None) and (req_.conflict == req.conflict) \
                            and (req_.weak == req.weak):
                        request[i] = req
                        del request_dict[req.name]
                    else:
                        request_.append(req)
                else:
                    request_.append(req)

            request += request_

        # add rank limiters
        if not strict and rank > 1:
            overrides = set(x.name for x in package_requests if not x.conflict)
            rank_limiters = []
            for variant in self.resolved_packages:
                if variant.name not in overrides:
                    if len(variant.version) >= rank:
                        version = variant.version.trim(rank - 1)
                        version = version.next()
                        req = "~%s<%s" % (variant.name, str(version))
                        rank_limiters.append(req)
            request += rank_limiters

        return request

    def graph(self, as_dot=False):
        """Get the resolve graph.

        Args:
            as_dot: If True, get the graph as a dot-language string. Otherwise,
                a pygraph.digraph object is returned.

        Returns:
            A string or `pygraph.digraph` object, or None if there is no graph
            associated with the resolve.
        """
        if not self.has_graph:
            return None

        if not as_dot:
            if self.graph_ is None:
                # reads either dot format or our compact format
                self.graph_ = read_graph_from_string(self.graph_string)
            return self.graph_

        if self.graph_string:
            if self.graph_string.startswith('{'):  # compact format
                self.graph_ = read_graph_from_string(self.graph_string)
            else:
                # already in dot format. Note that this will only happen in
                # old rez contexts where the graph is not stored in the newer
                # compact format.
                return self.graph_string

        return write_dot(self.graph_)

    def save(self, path):
        """Save the resolved context to file."""
        with open(path, 'w') as f:
            self.write_to_buffer(f)

    def write_to_buffer(self, buf):
        """Save the context to a buffer."""
        doc = self.to_dict()

        if config.rxt_as_yaml:
            content = dump_yaml(doc)
        else:
            content = json.dumps(doc, indent=4, separators=(",", ": "))

        buf.write(content)

    @classmethod
    def get_current(cls):
        """Get the context for the current env, if there is one.

        Returns:
            `ResolvedContext`: Current context, or None if not in a resolved env.
        """
        filepath = os.getenv("REZ_RXT_FILE")
        if not filepath or not os.path.exists(filepath):
            return None

        return cls.load(filepath)

    @classmethod
    def load(cls, path):
        """Load a resolved context from file."""
        with open(path) as f:
            context = cls.read_from_buffer(f, path)
        context.set_load_path(path)
        return context

    @classmethod
    def read_from_buffer(cls, buf, identifier_str=None):
        """Load the context from a buffer."""
        try:
            return cls._read_from_buffer(buf, identifier_str)
        except Exception as e:
            cls._load_error(e, identifier_str)

    def get_resolve_diff(self, other):
        """Get the difference between the resolve in this context and another.

        The difference is described from the point of view of the current context
        - a newer package means that the package in `other` is newer than the
        package in `self`.

        Diffs can only be compared if their package search paths match, an error
        is raised otherwise.

        The diff is expressed in packages, not variants - the specific variant
        of a package is ignored.

        Returns:
            A dict containing:
            - 'newer_packages': A dict containing items:
              - package name (str);
              - List of `Package` objects. These are the packages up to and
                including the newer package in `self`, in ascending order.
            - 'older_packages': A dict containing:
              - package name (str);
              - List of `Package` objects. These are the packages down to and
                including the older package in `self`, in descending order.
            - 'added_packages': Set of `Package` objects present in `self` but
               not in `other`;
            - 'removed_packages': Set of `Package` objects present in `other`,
               but not in `self`.

            If any item ('added_packages' etc) is empty, it is not added to the
            resulting dict. Thus, an empty dict is returned if there is no
            difference between contexts.
        """
        if self.package_paths != other.package_paths:
            from difflib import ndiff
            diff = ndiff(self.package_paths, other.package_paths)
            raise ResolvedContextError("Cannot diff resolves, package search "
                                       "paths differ:\n%s" % '\n'.join(diff))

        d = {}
        self_pkgs_ = set(x.parent for x in self._resolved_packages)
        other_pkgs_ = set(x.parent for x in other._resolved_packages)
        self_pkgs = self_pkgs_ - other_pkgs_
        other_pkgs = other_pkgs_ - self_pkgs_
        if not (self_pkgs or other_pkgs):
            return d

        self_fams = dict((x.name, x) for x in self_pkgs)
        other_fams = dict((x.name, x) for x in other_pkgs)

        newer_packages = {}
        older_packages = {}
        added_packages = set()
        removed_packages = set()

        for pkg in self_pkgs:
            if pkg.name not in other_fams:
                removed_packages.add(pkg)
            else:
                other_pkg = other_fams[pkg.name]
                if other_pkg.version > pkg.version:
                    r = VersionRange.as_span(lower_version=pkg.version,
                                             upper_version=other_pkg.version)
                    it = iter_packages(pkg.name, range_=r)
                    pkgs = sorted(it, key=lambda x: x.version)
                    newer_packages[pkg.name] = pkgs
                elif other_pkg.version < pkg.version:
                    r = VersionRange.as_span(lower_version=other_pkg.version,
                                             upper_version=pkg.version)
                    it = iter_packages(pkg.name, range_=r)
                    pkgs = sorted(it, key=lambda x: x.version, reverse=True)
                    older_packages[pkg.name] = pkgs

        for pkg in other_pkgs:
            if pkg.name not in self_fams:
                added_packages.add(pkg)

        if newer_packages:
            d["newer_packages"] = newer_packages
        if older_packages:
            d["older_packages"] = older_packages
        if added_packages:
            d["added_packages"] = added_packages
        if removed_packages:
            d["removed_packages"] = removed_packages
        return d

    @pool_memcached_connections
    def print_info(self, buf=sys.stdout, verbosity=0, source_order=False,
                   show_resolved_uris=False):
        """Prints a message summarising the contents of the resolved context.

        Args:
            buf (file-like object): Where to print this info to.
            verbosity (bool): Verbose mode.
            source_order (bool): If True, print resolved packages in the order
                they are sourced, rather than alphabetical order.
            show_resolved_uris (bool): By default, resolved packages have their
                'root' property listed, or their 'uri' if 'root' is None. Use
                this option to list 'uri' regardless.
        """
        _pr = Printer(buf)

        def _rt(t):
            if verbosity:
                s = time.strftime("%a %b %d %H:%M:%S %Z %Y", time.localtime(t))
                return s + " (%d)" % int(t)
            else:
                return time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(t))

        if self.status_ in (ResolverStatus.failed, ResolverStatus.aborted):
            _pr("The context failed to resolve:\n%s"
                % self.failure_description, critical)
            return

        t_str = _rt(self.created)
        _pr("resolved by %s@%s, on %s, using Rez v%s"
            % (self.user, self.host, t_str, self.rez_version))
        if self.requested_timestamp:
            t_str = _rt(self.requested_timestamp)
            _pr("packages released after %s were ignored" % t_str)
        _pr()

        if verbosity:
            _pr("search paths:", heading)
            rows = []
            colors = []
            for path in self.package_paths:
                if package_repository_manager.are_same(path, config.local_packages_path):
                    label = "(local)"
                    col = local
                else:
                    label = ""
                    col = None
                rows.append((path, label))
                colors.append(col)

            for col, line in zip(colors, columnise(rows)):
                _pr(line, col)
            _pr()

            if self.package_filter:
                data = self.package_filter.to_pod()
                txt = dump_yaml(data)
                _pr("package filters:", heading)
                _pr(txt)
                _pr()

        _pr("requested packages:", heading)
        rows = []
        colors = []
        for request in self._package_requests:
            rows.append((str(request), ""))
            colors.append(None)

        for request in self.implicit_packages:
            rows.append((str(request), "(implicit)"))
            colors.append(implicit)

        for col, line in zip(colors, columnise(rows)):
            _pr(line, col)
        _pr()

        _pr("resolved packages:", heading)
        rows = []
        colors = []

        resolved_packages = self.resolved_packages or []
        if not source_order:
            resolved_packages = sorted(resolved_packages, key=lambda x: x.name)

        for pkg in resolved_packages:
            t = []
            col = None
            location = None

            # print root/uri
            if show_resolved_uris or not pkg.root:
                location = pkg.uri
            else:
                location = pkg.root
                if not os.path.exists(pkg.root):
                    t.append('NOT FOUND')
                    col = critical

            if pkg.is_local:
                t.append('local')
                col = local

            t = '(%s)' % ', '.join(t) if t else ''
            rows.append((pkg.qualified_package_name, location, t))
            colors.append(col)

        for col, line in zip(colors, columnise(rows)):
            _pr(line, col)

        if verbosity:
            _pr()
            actual_solve_time = self.solve_time - self.load_time
            _pr("resolve details:", heading)
            _pr("load time:         %.02f secs" % self.load_time)
            _pr("solve time:        %.02f secs" % actual_solve_time)
            _pr("packages queried:  %d" % self.num_loaded_packages)
            _pr("from cache:        %s" % self.from_cache)
            if self.load_path:
                _pr("rxt file:          %s" % self.load_path)

        if verbosity >= 2:
            _pr()
            _pr("tools:", heading)
            self.print_tools(buf=buf)

    def print_tools(self, buf=sys.stdout):
        data = self.get_tools()
        if not data:
            return

        _pr = Printer(buf)
        conflicts = set(self.get_conflicting_tools().keys())
        rows = [["TOOL", "PACKAGE", ""],
                ["----", "-------", ""]]
        colors = [None, None]

        for _, (variant, tools) in sorted(data.items()):
            pkg_str = variant.qualified_package_name
            for tool in sorted(tools):
                col = None
                row = [tool, pkg_str, ""]
                if tool in conflicts:
                    col = critical
                    row[-1] = "(in conflict)"
                rows.append(row)
                colors.append(col)

        for col, line in zip(colors, columnise(rows)):
            _pr(line, col)

    def print_resolve_diff(self, other, heading=None):
        """Print the difference between the resolve of two contexts.

        Args:
            other (`ResolvedContext`): Context to compare to.
            heading: One of:
                - None: Do not display a heading;
                - True: Display the filename of each context as a heading, if
                  both contexts have a filepath;
                - 2-tuple: Use the given two strings as headings - the first is
                  the heading for `self`, the second for `other`.
        """
        d = self.get_resolve_diff(other)
        if not d:
            return

        rows = []
        if heading is True and self.load_path and other.load_path:
            a = os.path.basename(self.load_path)
            b = os.path.basename(other.load_path)
            heading = (a, b)
        if isinstance(heading, tuple):
            rows.append(list(heading) + [""])
            rows.append(('-' * len(heading[0]), '-' * len(heading[1]), ""))

        newer_packages = d.get("newer_packages", {})
        older_packages = d.get("older_packages", {})
        added_packages = d.get("added_packages", set())
        removed_packages = d.get("removed_packages", set())

        if newer_packages:
            for name, pkgs in newer_packages.items():
                this_pkg = pkgs[0]
                other_pkg = pkgs[-1]
                diff_str = "(+%d versions)" % (len(pkgs) - 1)
                rows.append((this_pkg.qualified_name,
                            other_pkg.qualified_name,
                            diff_str))

        if older_packages:
            for name, pkgs in older_packages.items():
                this_pkg = pkgs[0]
                other_pkg = pkgs[-1]
                diff_str = "(-%d versions)" % (len(pkgs) - 1)
                rows.append((this_pkg.qualified_name,
                            other_pkg.qualified_name,
                            diff_str))

        if added_packages:
            for pkg in sorted(added_packages, key=lambda x: x.name):
                rows.append(("-", pkg.qualified_name, ""))

        if removed_packages:
            for pkg in sorted(removed_packages, key=lambda x: x.name):
                rows.append((pkg.qualified_name, "-", ""))

        print('\n'.join(columnise(rows)))

    def _on_success(fn):
        @wraps(fn)
        def _check(self, *nargs, **kwargs):
            if self.status_ == ResolverStatus.solved:
                return fn(self, *nargs, **kwargs)
            else:
                raise ResolvedContextError(
                    "Cannot perform operation in a failed context")
        return _check

    @_on_success
    def get_dependency_graph(self):
        """Generate the dependency graph.

        The dependency graph is a simpler subset of the resolve graph. It
        contains package name nodes connected directly to their dependencies.
        Weak references and conflict requests are not included in the graph.
        The dependency graph does not show conflicts.

        Returns:
            `pygraph.digraph` object.
        """
        from rez.vendor.pygraph.classes.digraph import digraph

        nodes = {}
        edges = set()
        for variant in self._resolved_packages:
            nodes[variant.name] = variant.qualified_package_name
            for request in variant.get_requires():
                if not request.conflict:
                    edges.add((variant.name, request.name))

        g = digraph()
        node_color = "#AAFFAA"
        node_fontsize = 10
        attrs = [("fontsize", node_fontsize),
                 ("fillcolor", node_color),
                 ("style", "filled")]

        for name, qname in nodes.items():
            g.add_node(name, attrs=attrs + [("label", qname)])
        for edge in edges:
            g.add_edge(edge)
        return g

    @_on_success
    def validate(self):
        """Validate the context."""
        try:
            for pkg in self.resolved_packages:
                pkg.validate_data()
        except RezError as e:
            raise ResolvedContextError("%s: %s" % (e.__class__.__name__, str(e)))

    @_on_success
    def get_environ(self, parent_environ=None):
        """Get the environ dict resulting from interpreting this context.

        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @returns The environment dict generated by this context, when
            interpreted in a python rex interpreter.
        """
        interp = Python(target_environ={}, passive=True)
        executor = self._create_executor(interp, parent_environ)
        self._execute(executor)
        return executor.get_output()

    @_on_success
    def get_key(self, key, request_only=False):
        """Get a data key value for each resolved package.

        Args:
            key (str): String key of property, eg 'tools'.
            request_only (bool): If True, only return the key from resolved
                packages that were also present in the request.

        Returns:
            Dict of {pkg-name: (variant, value)}.
        """
        values = {}
        requested_names = [x.name for x in self._package_requests
                           if not x.conflict]

        for pkg in self.resolved_packages:
            if (not request_only) or (pkg.name in requested_names):
                value = getattr(pkg, key)
                if value is not None:
                    values[pkg.name] = (pkg, value)

        return values

    @_on_success
    def get_tools(self, request_only=False):
        """Returns the commandline tools available in the context.

        Args:
            request_only: If True, only return the tools from resolved packages
                that were also present in the request.

        Returns:
            Dict of {pkg-name: (variant, [tools])}.
        """
        return self.get_key("tools", request_only=request_only)

    @_on_success
    def get_tool_variants(self, tool_name):
        """Get the variant(s) that provide the named tool.

        If there are more than one variants, the tool is in conflict, and Rez
        does not know which variant's tool is actually exposed.

        Args:
            tool_name(str): Name of the tool to search for.

        Returns:
            Set of `Variant` objects. If no variant provides the tool, an
            empty set is returned.
        """
        variants = set()
        tools_dict = self.get_tools(request_only=False)
        for variant, tools in tools_dict.values():
            if tool_name in tools:
                variants.add(variant)
        return variants

    @_on_success
    def get_conflicting_tools(self, request_only=False):
        """Returns tools of the same name provided by more than one package.

        Args:
            request_only: If True, only return the key from resolved packages
                that were also present in the request.

        Returns:
            Dict of {tool-name: set([Variant])}.
        """
        from collections import defaultdict

        tool_sets = defaultdict(set)
        tools_dict = self.get_tools(request_only=request_only)
        for variant, tools in tools_dict.values():
            for tool in tools:
                tool_sets[tool].add(variant)

        conflicts = dict((k, v) for k, v in tool_sets.items() if len(v) > 1)
        return conflicts

    @_on_success
    def get_shell_code(self, shell=None, parent_environ=None, style=OutputStyle.file):
        """Get the shell code resulting from intepreting this context.

        Args:
            shell (str): Shell type, for eg 'bash'. If None, the current shell
                type is used.
            parent_environ (dict): Environment to interpret the context within,
                defaults to os.environ if None.
            style (): Style to format shell code in.
        """
        executor = self._create_executor(interpreter=create_shell(shell),
                                         parent_environ=parent_environ)

        if self.load_path and os.path.isfile(self.load_path):
            executor.env.REZ_RXT_FILE = self.load_path

        self._execute(executor)
        return executor.get_output(style)

    @_on_success
    def get_actions(self, parent_environ=None):
        """Get the list of rex.Action objects resulting from interpreting this
        context. This is provided mainly for testing purposes.

        Args:
            parent_environ Environment to interpret the context within,
                defaults to os.environ if None.

        Returns:
            A list of rex.Action subclass instances.
        """
        interp = Python(target_environ={}, passive=True)
        executor = self._create_executor(interp, parent_environ)
        self._execute(executor)
        return executor.actions

    @_on_success
    def apply(self, parent_environ=None):
        """Apply the context to the current python session.

        Note that this updates os.environ and possibly sys.path, if
        `parent_environ` is not provided.

        Args:
            parent_environ: Environment to interpret the context within,
                defaults to os.environ if None.
        """
        interpreter = Python(target_environ=os.environ)
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)
        interpreter.apply_environ()

    @_on_success
    def which(self, cmd, parent_environ=None, fallback=False):
        """Find a program in the resolved environment.

        Args:
            cmd: String name of the program to find.
            parent_environ: Environment to interpret the context within,
                defaults to os.environ if None.
            fallback: If True, and the program is not found in the context,
                the current environment will then be searched.

        Returns:
            Path to the program, or None if the program was not found.
        """
        env = self.get_environ(parent_environ=parent_environ)
        path = which(cmd, env=env)
        if fallback and path is None:
            path = which(cmd)
        return path

    @_on_success
    def execute_command(self, args, parent_environ=None, **subprocess_kwargs):
        """Run a command within a resolved context.

        This applies the context to a python environ dict, then runs a
        subprocess in that namespace. This is not a fully configured subshell -
        shell-specific commands such as aliases will not be applied. To execute
        a command within a subshell instead, use execute_shell().

        Warning:
            This runs a command in a configured environ dict only, not in a true
            shell. To do that, call `execute_shell` using the `command` keyword
            argument.

        Args:
            args: Command arguments, can be a string.
            parent_environ: Environment to interpret the context within,
                defaults to os.environ if None.
            subprocess_kwargs: Args to pass to subprocess.Popen.

        Returns:
            A subprocess.Popen object.

        Note:
            This does not alter the current python session.
        """
        if parent_environ in (None, os.environ):
            target_environ = {}
        else:
            target_environ = parent_environ.copy()

        interpreter = Python(target_environ=target_environ)

        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)
        return interpreter.subprocess(args, **subprocess_kwargs)

    @_on_success
    def execute_rex_code(self, code, filename=None, shell=None,
                         parent_environ=None, **Popen_args):
        """Run some rex code in the context.

        Note:
            This is just a convenience form of `execute_shell`.

        Args:
            code (str): Rex code to execute.
            filename (str): Filename to report if there are syntax errors.
            shell: Shell type, for eg 'bash'. If None, the current shell type
                is used.
            parent_environ: Environment to run the shell process in, if None
                then the current environment is used.
            Popen_args: args to pass to the shell process object constructor.

        Returns:
            `subprocess.Popen` object for the shell process.
        """
        def _actions_callback(executor):
            executor.execute_code(code, filename=filename)

        return self.execute_shell(shell=shell,
                                  parent_environ=parent_environ,
                                  command='',  # don't run any command
                                  block=False,
                                  actions_callback=_actions_callback,
                                  **Popen_args)

    @_on_success
    def execute_shell(self, shell=None, parent_environ=None, rcfile=None,
                      norc=False, stdin=False, command=None, quiet=False,
                      block=None, actions_callback=None, post_actions_callback=None,
                      context_filepath=None, start_new_session=False, detached=False,
                      pre_command=None, **Popen_args):
        """Spawn a possibly-interactive shell.

        Args:
            shell: Shell type, for eg 'bash'. If None, the current shell type
                is used.
            parent_environ: Environment to run the shell process in, if None
                then the current environment is used.
            rcfile: Specify a file to source instead of shell startup files.
            norc: If True, skip shell startup files, if possible.
            stdin: If True, read commands from stdin, in a non-interactive
                shell.
            command: If not None, execute this command in a non-interactive shell.
                If an empty string or list, don't run a command, but don't open
                an interactive shell either. Can be a list of args.
            quiet: If True, skip the welcome message in interactive shells.
            block: If True, block until the shell is terminated. If False,
                return immediately. If None, will default to blocking if the
                shell is interactive.
            actions_callback: Callback with signature (RexExecutor). This lets
                the user append custom actions to the context, such as setting
                extra environment variables. Callback is run prior to context Rex
                execution.
            post_actions_callback: Callback with signature (RexExecutor). This lets
                the user append custom actions to the context, such as setting
                extra environment variables. Callback is run after context Rex
                execution.
            context_filepath: If provided, the context file will be written
                here, rather than to the default location (which is in a
                tempdir). If you use this arg, you are responsible for cleaning
                up the file.
            start_new_session: If True, change the process group of the target
                process. Note that this may override the Popen_args keyword
                'preexec_fn'.
            detached: If True, open a separate terminal. Note that this may
                override the `pre_command` argument.
            pre_command: Command to inject before the shell command itself. This
                is for internal use.
            Popen_args: args to pass to the shell process object constructor.

        Returns:
            If blocking: A 3-tuple of (returncode, stdout, stderr);
            If non-blocking - A subprocess.Popen object for the shell process.
        """
        sh = create_shell(shell)

        is_iterable = hasattr(command, "__iter__")
        is_string = isinstance(command, six.string_types)

        # In Python 2, a string does not have `__iter__`
        if is_iterable and not is_string:
            command = sh.join(command)

        # start a new session if specified
        if start_new_session:
            Popen_args.update(config.new_session_popen_args)

        # open a separate terminal if specified
        if detached:
            term_cmd = config.terminal_emulator_command
            if term_cmd:
                pre_command = term_cmd.strip().split()

        # block if the shell is likely to be interactive
        if block is None:
            block = not (command or stdin)

        # context and rxt files. If running detached, don't cleanup files, because
        # rez-env returns too early and deletes the tmp files before the detached
        # process can use them
        tmpdir = self.tmpdir_manager.mkdtemp(cleanup=not detached)

        if self.load_path and os.path.isfile(self.load_path):
            rxt_file = self.load_path
        else:
            rxt_file = os.path.join(tmpdir, "context.rxt")
            self.save(rxt_file)

        context_file = context_filepath or \
            os.path.join(tmpdir, "context.%s" % sh.file_extension())

        # interpret this context and write out the native context file
        executor = self._create_executor(sh, parent_environ)
        executor.env.REZ_RXT_FILE = rxt_file
        executor.env.REZ_CONTEXT_FILE = context_file

        if actions_callback:
            actions_callback(executor)

        self._execute(executor)

        if post_actions_callback:
            post_actions_callback(executor)

        context_code = executor.get_output()
        with open(context_file, 'w') as f:
            f.write(context_code)

        quiet = quiet or \
            (RezToolsVisibility[config.rez_tools_visibility] == RezToolsVisibility.never)

        # spawn the shell subprocess
        p = sh.spawn_shell(context_file,
                           tmpdir,
                           rcfile=rcfile,
                           norc=norc,
                           stdin=stdin,
                           command=command,
                           env=parent_environ,
                           quiet=quiet,
                           pre_command=pre_command,
                           **Popen_args)
        if block:
            stdout, stderr = p.communicate()
            return p.returncode, stdout, stderr
        else:
            return p

    def to_dict(self, fields=None):
        """Convert context to dict containing only builtin types.

        Args:
            fields (list of str): If present, only write these fields into the
                dict. This can be used to avoid constructing expensive fields
                (such as 'graph') for some cases.

        Returns:
            dict: Dictified context.
        """
        data = {}

        def _add(field):
            return (fields is None or field in fields)

        if _add("resolved_packages"):
            resolved_packages = []
            for pkg in (self._resolved_packages or []):
                resolved_packages.append(pkg.handle.to_dict())
            data["resolved_packages"] = resolved_packages

        if _add("serialize_version"):
            data["serialize_version"] = \
                '.'.join(map(str, ResolvedContext.serialize_version))

        if _add("patch_locks"):
            data["patch_locks"] = dict((k, v.name) for k, v in self.patch_locks)

        if _add("package_orderers"):
            package_orderers = [package_order.to_pod(x)
                                for x in (self.package_orderers or [])]
            data["package_orderers"] = package_orderers or None

        if _add("package_filter"):
            data["package_filter"] = self.package_filter.to_pod()

        if _add("graph"):
            if self.graph_string and self.graph_string.startswith('{'):
                graph_str = self.graph_string  # already in compact format
            else:
                g = self.graph()
                graph_str = write_compacted(g)

            data["graph"] = graph_str

        data.update(dict(
            timestamp=self.timestamp,
            requested_timestamp=self.requested_timestamp,
            building=self.building,
            caching=self.caching,
            implicit_packages=list(map(str, self.implicit_packages)),
            package_requests=list(map(str, self._package_requests)),
            package_paths=self.package_paths,

            default_patch_lock=self.default_patch_lock.name,

            rez_version=self.rez_version,
            rez_path=self.rez_path,
            user=self.user,
            host=self.host,
            platform=self.platform,
            arch=self.arch,
            os=self.os,
            created=self.created,

            parent_suite_path=self.parent_suite_path,
            suite_context_name=self.suite_context_name,

            status=self.status_.name,
            failure_description=self.failure_description,

            from_cache=self.from_cache,
            solve_time=self.solve_time,
            load_time=self.load_time,
            num_loaded_packages=self.num_loaded_packages
        ))

        if fields:
            data = dict((k, v) for k, v in data.items() if k in fields)

        return data

    @classmethod
    def from_dict(cls, d, identifier_str=None):
        """Load a `ResolvedContext` from a dict.

        Args:
            d (dict): Dict containing context data.
            identifier_str (str): String identifying the context, this is only
                used to display in an error string if a serialization version
                mismatch is detected.

        Returns:
            `ResolvedContext` object.
        """
        # check serialization version
        def _print_version(value):
            return '.'.join(str(x) for x in value)

        toks = str(d["serialize_version"]).split('.')
        load_ver = tuple(int(x) for x in toks)
        curr_ver = ResolvedContext.serialize_version

        if load_ver[0] > curr_ver[0]:
            msg = ["The context"]
            if identifier_str:
                msg.append("in %s" % identifier_str)
            msg.append("was written by a newer version of Rez. The load may "
                       "fail (serialize version %d > %d)"
                       % (_print_version(load_ver), _print_version(curr_ver)))
            print(' '.join(msg), file=sys.stderr)

        # create and init the context
        r = ResolvedContext.__new__(ResolvedContext)
        r.load_path = None
        r.pre_resolve_bindings = None

        r.timestamp = d["timestamp"]
        r.building = d["building"]
        r.caching = d["caching"]
        r.implicit_packages = [PackageRequest(x) for x in d["implicit_packages"]]
        r._package_requests = [PackageRequest(x) for x in d["package_requests"]]
        r.package_paths = d["package_paths"]

        r.rez_version = d["rez_version"]
        r.rez_path = d["rez_path"]
        r.user = d["user"]
        r.host = d["host"]
        r.platform = d["platform"]
        r.arch = d["arch"]
        r.os = d["os"]
        r.created = d["created"]
        r.verbosity = d.get("verbosity", 0)

        r.status_ = ResolverStatus[d["status"]]
        r.failure_description = d["failure_description"]

        r.solve_time = d["solve_time"]
        r.load_time = d["load_time"]

        r.graph_string = d["graph"]
        r.graph_ = None

        r._resolved_packages = []
        for d_ in d["resolved_packages"]:
            variant_handle = d_
            if load_ver < (4, 0):
                # -- SINCE SERIALIZE VERSION 4.0
                from rez.utils.backcompat import convert_old_variant_handle
                variant_handle = convert_old_variant_handle(variant_handle)

            variant = get_variant(variant_handle)
            variant.set_context(r)
            r._resolved_packages.append(variant)

        # -- SINCE SERIALIZE VERSION 1

        r.requested_timestamp = d.get("requested_timestamp", 0)

        # -- SINCE SERIALIZE VERSION 2

        r.parent_suite_path = d.get("parent_suite_path")
        r.suite_context_name = d.get("suite_context_name")

        # -- SINCE SERIALIZE VERSION 3

        r.default_patch_lock = PatchLock[d.get("default_patch_lock", "no_lock")]
        patch_locks = d.get("patch_locks", {})
        r.patch_locks = dict((k, PatchLock[v]) for k, v in patch_locks)

        # -- SINCE SERIALIZE VERSION 4.0

        r.from_cache = d.get("from_cache", False)

        # -- SINCE SERIALIZE VERSION 4.1

        data = d.get("package_filter", [])
        r.package_filter = PackageFilterList.from_pod(data)

        # -- SINCE SERIALIZE VERSION 4.2

        data = d.get("package_orderers")
        if data:
            r.package_orderers = [package_order.from_pod(x) for x in data]
        else:
            r.package_orderers = None

        # -- SINCE SERIALIZE VERSION 4.3

        r.num_loaded_packages = d.get("num_loaded_packages", -1)

        # track context usage
        if config.context_tracking_host:
            data = dict((k, v) for k, v in d.items()
                        if k in config.context_tracking_context_fields)

            r._track_context(data, action="sourced")

        return r

    @classmethod
    def _init_context_tracking_payload_base(cls):
        if cls.context_tracking_payload is not None:
            return

        data = {
            "host": socket.gethostname(),
            "user": getpass.getuser()
        }

        data.update(config.context_tracking_extra_fields or {})

        # remove fields with unexpanded env-vars, or empty string
        def _del(value):
            return (
                isinstance(value, six.string_types) and
                (not value or ENV_VAR_REGEX.search(value))
            )

        data = deep_del(data, _del)

        with cls.context_tracking_lock:
            if cls.context_tracking_payload is None:
                cls.context_tracking_payload = data

    def _track_context(self, context_data, action):
        from rez.utils.amqp import publish_message

        # create message payload
        data = {
            "action": action,
            "context": context_data
        }

        self._init_context_tracking_payload_base()
        data.update(self.context_tracking_payload)

        # publish message
        routing_key = (config.context_tracking_amqp["exchange_routing_key"] +
                       '.' + action.upper())

        publish_message(
            host=config.context_tracking_host,
            amqp_settings=config.context_tracking_amqp,
            routing_key=routing_key,
            data=data,
            block=False
        )

    @classmethod
    def _read_from_buffer(cls, buf, identifier_str=None):
        content = buf.read()

        if content.startswith('{'):  # assume json content
            doc = json.loads(content)
        else:
            doc = yaml.load(content)

        context = cls.from_dict(doc, identifier_str)
        return context

    @classmethod
    def _load_error(cls, e, path=None):
        exc_name = e.__class__.__name__
        msg = "Failed to load context"
        if path:
            msg += " from %s" % path
        raise ResolvedContextError("%s: %s: %s" % (msg, exc_name, str(e)))

    def _set_parent_suite(self, suite_path, context_name):
        self.parent_suite_path = suite_path
        self.suite_context_name = context_name

    def _create_executor(self, interpreter, parent_environ):
        parent_vars = True if config.all_parent_variables \
            else config.parent_variables

        return RexExecutor(interpreter=interpreter,
                           parent_environ=parent_environ,
                           parent_variables=parent_vars)

    def _get_pre_resolve_bindings(self):
        if self.pre_resolve_bindings is None:
            self.pre_resolve_bindings = {
                "system": system,
                "building": self.building,
                "request": RequirementsBinding(self._package_requests),
                "implicits": RequirementsBinding(self.implicit_packages)
            }

        return self.pre_resolve_bindings

    @pool_memcached_connections
    def _execute(self, executor):
        br = '#' * 80
        br_minor = '-' * 80

        def _heading(txt):
            executor.comment("")
            executor.comment("")
            executor.comment(br)
            executor.comment(txt)
            executor.comment(br)

        def _minor_heading(txt):
            executor.comment("")
            executor.comment(txt)
            executor.comment(br_minor)

        # bind various info to the execution context
        resolved_pkgs = self.resolved_packages or []
        request_str = ' '.join(str(x) for x in self._package_requests)
        implicit_str = ' '.join(str(x) for x in self.implicit_packages)
        resolve_str = ' '.join(x.qualified_package_name for x in resolved_pkgs)
        package_paths_str = os.pathsep.join(self.package_paths)

        _heading("system setup")
        executor.setenv("REZ_USED", self.rez_path)
        executor.setenv("REZ_USED_VERSION", self.rez_version)
        executor.setenv("REZ_USED_TIMESTAMP", str(self.timestamp))
        executor.setenv("REZ_USED_REQUESTED_TIMESTAMP",
                        str(self.requested_timestamp or 0))
        executor.setenv("REZ_USED_REQUEST", request_str)
        executor.setenv("REZ_USED_IMPLICIT_PACKAGES", implicit_str)
        executor.setenv("REZ_USED_RESOLVE", resolve_str)
        executor.setenv("REZ_USED_PACKAGES_PATH", package_paths_str)

        if self.building:
            executor.setenv("REZ_BUILD_ENV", "1")

        # rez-1 environment variables, set in backwards compatibility mode
        if config.rez_1_environment_variables and \
                not config.disable_rez_1_compatibility:
            request_str_ = " ".join([request_str, implicit_str]).strip()
            executor.setenv("REZ_VERSION", self.rez_version)
            executor.setenv("REZ_PATH", self.rez_path)
            executor.setenv("REZ_REQUEST", request_str_)
            executor.setenv("REZ_RESOLVE", resolve_str)
            executor.setenv("REZ_RAW_REQUEST", request_str_)
            executor.setenv("REZ_RESOLVE_MODE", "latest")

        # binds objects such as 'request', which are accessible before a resolve
        bindings = self._get_pre_resolve_bindings()
        for k, v in bindings.items():
            executor.bind(k, v)

        executor.bind('resolve', VariantsBinding(resolved_pkgs))

        #
        # -- apply each resolved package to the execution context
        #

        _heading("package variables")
        error_class = SourceCodeError if config.catch_rex_errors else None

        # set basic package variables and create per-package bindings
        bindings = {}
        for pkg in resolved_pkgs:
            _minor_heading("variables for package %s" % pkg.qualified_name)
            prefix = "REZ_" + pkg.name.upper().replace('.', '_')

            executor.setenv(prefix + "_VERSION", str(pkg.version))
            major_version = str(pkg.version[0] if len(pkg.version) >= 1 else '')
            minor_version = str(pkg.version[1] if len(pkg.version) >= 2 else '')
            patch_version = str(pkg.version[2] if len(pkg.version) >= 3 else '')
            executor.setenv(prefix + "_MAJOR_VERSION", major_version)
            executor.setenv(prefix + "_MINOR_VERSION", minor_version)
            executor.setenv(prefix + "_PATCH_VERSION", patch_version)

            executor.setenv(prefix + "_BASE", pkg.base)
            executor.setenv(prefix + "_ROOT", pkg.root)
            bindings[pkg.name] = dict(version=VersionBinding(pkg.version),
                                      variant=VariantBinding(pkg))

        # commands
        for attr in ("pre_commands", "commands", "post_commands"):
            found = False
            for pkg in resolved_pkgs:
                commands = getattr(pkg, attr)
                if commands is None:
                    continue
                if not found:
                    found = True
                    _heading(attr)

                _minor_heading("%s from package %s" % (attr, pkg.qualified_name))
                bindings_ = bindings[pkg.name]
                executor.bind('this',       bindings_["variant"])
                executor.bind("version",    bindings_["version"])
                executor.bind('root',       pkg.root)
                executor.bind('base',       pkg.base)

                exc = None
                trace = None
                commands.set_package(pkg)

                try:
                    executor.execute_code(commands, isolate=True)
                except error_class as e:
                    exc = e

                if exc:
                    header = "Error in %s in package %r:\n" % (attr, pkg.uri)
                    if self.verbosity >= 2:
                        msg = header + str(exc)
                    else:
                        msg = header + exc.short_msg

                    raise PackageCommandError(msg)

        _heading("post system setup")

        # append suite paths based on suite visibility setting
        self._append_suite_paths(executor)

        # append system paths
        executor.append_system_paths()

        # add rez path so that rez commandline tools are still available within
        # the resolved environment
        mode = RezToolsVisibility[config.rez_tools_visibility]
        if mode == RezToolsVisibility.append:
            executor.append_rez_path()
        elif mode == RezToolsVisibility.prepend:
            executor.prepend_rez_path()

    def _append_suite_paths(self, executor):
        from rez.suite import Suite

        mode = SuiteVisibility[config.suite_visibility]
        if mode == SuiteVisibility.never:
            return

        visible_suite_paths = Suite.visible_suite_paths()
        if not visible_suite_paths:
            return

        suite_paths = []
        if mode == SuiteVisibility.always:
            suite_paths = visible_suite_paths
        elif self.parent_suite_path:
            if mode == SuiteVisibility.parent:
                suite_paths = [self.parent_suite_path]
            elif mode == SuiteVisibility.parent_priority:
                pop_parent = None
                try:
                    parent_index = visible_suite_paths.index(self.parent_suite_path)
                    pop_parent = visible_suite_paths.pop(parent_index)
                except ValueError:
                    pass
                suite_paths.insert(0, (pop_parent or self.parent_suite_path))

        for path in suite_paths:
            tools_path = os.path.join(path, "bin")
            executor.env.PATH.append(tools_path)


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
