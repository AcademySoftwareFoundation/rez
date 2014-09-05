from rez import __version__, module_root_path
from rez.resolver import Resolver, ResolverStatus
from rez.system import system
from rez.config import config
from rez.colorize import critical, error, heading, local, implicit, Printer
from rez.resources import ResourceHandle
from rez.util import columnise, convert_old_commands, shlex_join, \
    mkdtemp_, rmdtemp, _add_bootstrap_pkg_path, dedup, timings
from rez.vendor.pygraph.readwrite.dot import write as write_dot
from rez.vendor.pygraph.readwrite.dot import read as read_dot
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.version import VersionRange
from rez.backport.shutilwhich import which
from rez.rex import RexExecutor, Python, OutputStyle
from rez.rex_bindings import VersionBinding, VariantBinding, \
    VariantsBinding, RequirementsBinding
from rez.packages import Variant, validate_package_name, iter_packages
from rez.shells import create_shell, get_shell_types
from rez.exceptions import ResolvedContextError, PackageCommandError, RezError
from rez.vendor.enum import Enum
from rez.vendor import yaml
import getpass
import inspect
import time
import uuid
import sys
import os
import os.path


class PatchLock(Enum):
    """ Enum to represent the 'lock type' used when patching context objects.
    """
    no_lock = ("No locking",)
    lock_2 = ("Minor version updates only (rank 2)",)
    lock_3 = ("Patch version updates only (rank 3)",)
    lock_4 = ("Build version updates only (rank 4)",)
    lock = ("Exact version",)

    __order__ = "no_lock,lock_2,lock_3,lock_4,lock"

    def __init__(self, description):
        self.description = description


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
    serialize_version = 3

    class Callback(object):
        def __init__(self, verbose, max_fails, time_limit, callback, buf=None):
            self.verbose = verbose
            self.max_fails = max_fails
            self.time_limit = time_limit
            self.callback = callback
            self.start_time = time.time()
            self.buf = buf or sys.stdout

        def __call__(self, state):
            if self.verbose:
                print >> self.buf, state
            if self.max_fails != -1 and state.num_fails >= self.max_fails:
                return False, ("fail limit reached: aborted after %d failures"
                               % state.num_fails)
            if self.time_limit != -1:
                secs = time.time() - self.start_time
                if secs > self.time_limit:
                    return False, "time limit exceeded"
            if self.callback:
                return self.callback(state)
            return True, ''

    def __init__(self, package_requests, verbosity=0, timestamp=None,
                 building=False, caching=None, package_paths=None,
                 add_implicit_packages=True, add_bootstrap_path=None,
                 max_fails=-1, time_limit=-1, callback=None,
                 package_load_callback=None, buf=None):
        """Perform a package resolve, and store the result.

        Args:
            package_requests: List of strings or Requirement objects
                representing the request.
            verbosity: Verbosity level. One of [0,1,2].
            timestamp: Ignore packages released after this epoch time. Packages
                released at exactly this time will not be ignored.
            building: True if we're resolving for a build.
            caching: If True, cache(s) may be used to speed the resolve. If
                False, caches will not be used. If None, defaults to
                config.resolve_caching.
            package_paths: List of paths to search for pkgs, defaults to
                config.packages_path.
            add_implicit_packages: If True, the implicit package list defined
                by config.implicit_packages is appended to the request.
            add_bootstrap_path: If True, append the package search path with
                the bootstrap path. If False, do not append. If None, use the
                default specified in config.add_bootstrap_path.
            max_fails (int): Abort the resolve after this many failed
                resolve steps. If -1, does not abort.
            time_limit (int): Abort the resolve if it takes longer than this
                many seconds. If -1, there is no time limit.
            callback: If not None, this callable will be called after each
                solve step. It is passed a `SolverState` object. It must return
                a 2-tuple:
                - bool: If True, continue the solve, otherwise abort;
                - str: Reason for solve abort, ignored if solve not aborted.
            package_load_callback: If not None, this callable will be called
                prior to each package being loaded. It is passed a single
                `Package` object.
            buf (file-like object): Where to print verbose output to, defaults
                to stdout.
        """
        self.load_path = None

        # resolving settings
        self.requested_timestamp = timestamp
        self.timestamp = self.requested_timestamp or int(time.time())
        self.building = building
        self.implicit_packages = []
        self.caching = config.resolve_caching if caching is None else caching

        self._package_requests = []
        for req in package_requests:
            if isinstance(req, basestring):
                req = Requirement(req)
            self._package_requests.append(req)

        if add_implicit_packages:
            self.implicit_packages = [Requirement(x)
                                      for x in config.implicit_packages]
        # package paths
        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)
        add_bootstrap = (config.add_bootstrap_path
                         if add_bootstrap_path is None else add_bootstrap_path)
        if add_bootstrap:
            self.package_paths = _add_bootstrap_pkg_path(self.package_paths)
        self.package_paths = list(dedup(self.package_paths))

        # patch settings
        self.default_patch_lock = PatchLock.no_lock
        self.patch_locks = {}

        # info about env the resolve occurred in
        self.rez_version = __version__
        self.rez_path = module_root_path
        self.user = getpass.getuser()
        self.host = system.fqdn
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
        self.solve_time = 0.0
        self.load_time = 0.0

        # suite information
        self.parent_suite_path = None
        self.suite_context_name = None

        # perform the solve
        verbose_ = False
        print_state = False
        if verbosity >= 1:
            print_state = True
        if verbosity == 2:
            verbose_ = True

        callback_ = self.Callback(verbose=print_state,
                                  buf=buf,
                                  max_fails=max_fails,
                                  time_limit=time_limit,
                                  callback=callback)

        request = self.requested_packages(include_implicit=True)

        resolver = Resolver(package_requests=request,
                            package_paths=self.package_paths,
                            timestamp=self.timestamp,
                            building=self.building,
                            caching=caching,
                            callback=callback_,
                            package_load_callback=package_load_callback,
                            verbose=verbose_,
                            buf=buf)
        resolver.solve()

        # convert the results
        self.status_ = resolver.status
        self.solve_time = resolver.solve_time
        self.load_time = resolver.load_time
        self.failure_description = resolver.failure_description
        self.graph_ = resolver.graph

        actual_solve_time = self.solve_time - self.load_time
        timings.add("resolve", actual_solve_time)

        if self.status_ == ResolverStatus.solved:
            # convert solver.Variants to packages.Variants
            pkgs = []
            for variant in resolver.resolved_packages:
                resource_handle = variant.userdata
                resource = resource_handle.get_resource()
                pkg = Variant(resource)
                pkgs.append(pkg)
            self._resolved_packages = pkgs

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
            List of `Requirement` objects.
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
        return ((self.graph_ is not None) or self.graph_string)

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

    # TODO deprecate in favor of patch() method
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
            package_requests (list of str or list of `Requirement`):
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
            List of `Requirement` objects that can be used to construct a new
            `ResolvedContext` object.
        """
        # assemble source request
        if strict:
            request = []
            for variant in self.resolved_packages:
                req = Requirement(variant.qualified_package_name)
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
            for pkg_name in package_subtractions:
                validate_package_name(pkg_name)
            request = [x for x in request if x.name not in package_subtractions]

        # apply overrides
        if package_requests:
            request_dict = dict((x.name, (i, x)) for i, x in enumerate(request))
            request_ = []

            for req in package_requests:
                if isinstance(req, basestring):
                    req = Requirement(req)

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
            A string or pygraph.digraph object, or None if there is no graph
            associated with the resolve.
        """
        if not self.has_graph:
            return None
        elif as_dot:
            if not self.graph_string:
                self.graph_string = write_dot(self.graph_)
            return self.graph_string
        elif self.graph_ is None:
            self.graph_ = read_dot(self.graph_string)

        return self.graph_

    def save(self, path):
        """Save the resolved context to file."""
        doc = self.to_dict()
        content = yaml.dump(doc)
        with open(path, 'w') as f:
            f.write(content)

    @classmethod
    def load(cls, path):
        """Load a resolved context from file."""
        try:
            return cls._load(path)
        except Exception as e:
            raise ResolvedContextError("Failed to load context from %r: %s: %s"
                                       % (path, e.__class__.__name__, str(e)))

    @classmethod
    def _load(cls, path):
        with open(path) as f:
            doc = yaml.load(f.read())

        load_ver = doc["serialize_version"]
        curr_ver = ResolvedContext.serialize_version
        if load_ver > curr_ver:
            print >> sys.stderr, \
                ("The context stored in %s was written by a newer version of "
                 "Rez. The load may fail (serialize version %d > %d)"
                 % (path, load_ver, curr_ver), critical)

        r = cls.from_dict(doc)
        r.load_path = os.path.abspath(path)
        return r

    def get_resolve_diff(self, other):
        """Get the difference between the resolve in this context and another.

        Diffs can only be compared if their package search paths match, an error
        is raised otherwise.

        The diff is expressed in packages, not variants - the specific variant
        of a package is ignored.

        Returns:
            A dict containing:
            - 'newer_packages': A dict containing items:
              - package name (str);
              - List of `Package` objects. These are the packages up to and
                including the newer package in `other`, in ascending order.
            - 'older_packages': A dict containing:
              - package name (str);
              - List of `Package` objects. These are the packages down to and
                including the older package in `other`, in descending order.
            - 'added_packages': Set of `Package` objects present in `other` but
               not in this context;
            - 'removed_packages': Set of `Package` objects present in this
               context but not in `other`.

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
                    it = iter_packages(pkg.name, range=r)
                    pkgs = sorted(it, key=lambda x: x.version)
                    newer_packages[pkg.name] = pkgs
                elif other_pkg.version < pkg.version:
                    r = VersionRange.as_span(lower_version=other_pkg.version,
                                             upper_version=pkg.version)
                    it = iter_packages(pkg.name, range=r)
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

    def print_info(self, buf=sys.stdout, verbosity=0):
        """Prints a message summarising the contents of the resolved context.
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
            rows = []
            colors = []
            local_packages_path = os.path.realpath(config.local_packages_path)
            _pr("search paths:", heading)

            for path in self.package_paths:
                label = ""
                col = None
                path_ = os.path.realpath(path)
                if not os.path.exists(path_):
                    label = "(NOT FOUND)"
                    col = critical
                elif path_ == local_packages_path:
                    label = "(local)"
                    col = local
                rows.append((path, label))
                colors.append(col)

            for col, line in zip(colors, columnise(rows)):
                _pr(line, col)
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
        for pkg in (self.resolved_packages or []):
            t = []
            col = None
            if not os.path.exists(pkg.root):
                t.append('NOT FOUND')
                col = critical
            if pkg.is_local:
                t.append('local')
                col = local
            t = '(%s)' % ', '.join(t) if t else ''
            rows.append((pkg.qualified_package_name, pkg.root, t))
            colors.append(col)

        for col, line in zip(colors, columnise(rows)):
            _pr(line, col)

        if verbosity:
            _pr()
            _pr("resolve details:", heading)
            _pr("load time: %.02f secs" % self.load_time)
            actual_solve_time = self.solve_time - self.load_time
            _pr("solve time: %.02f secs" % actual_solve_time)
            if self.load_path:
                _pr("rxt file: %s" % self.load_path)

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

    def print_resolve_diff(self, other):
        """Print the difference between the resolve of two contexts."""
        d = self.get_resolve_diff(other)
        if not d:
            return

        rows = []
        newer_packages = d.get("newer_packages", {})
        older_packages = d.get("older_packages", {})
        added_packages = d.get("added_packages", set())
        removed_packages = d.get("removed_packages", set())

        if newer_packages:
            for name, pkgs in newer_packages.iteritems():
                this_pkg = pkgs[0]
                other_pkg = pkgs[-1]
                other_pkg_str = ("%s (+%d versions)"
                                 % (other_pkg.qualified_name, len(pkgs) - 1))
                rows.append((this_pkg.qualified_name, other_pkg_str))

        if older_packages:
            for name, pkgs in older_packages.iteritems():
                this_pkg = pkgs[0]
                other_pkg = pkgs[-1]
                other_pkg_str = ("%s (-%d versions)"
                                 % (other_pkg.qualified_name, len(pkgs) - 1))
                rows.append((this_pkg.qualified_name, other_pkg_str))

        if added_packages:
            for pkg in sorted(added_packages, key=lambda x: x.name):
                rows.append(("-", pkg.qualified_name))

        if removed_packages:
            for pkg in sorted(removed_packages, key=lambda x: x.name):
                rows.append((pkg.qualified_name, "-"))

        print '\n'.join(columnise(rows))

    def _on_success(fn):
        def _check(self, *nargs, **kwargs):
            if self.status_ == ResolverStatus.solved:
                return fn(self, *nargs, **kwargs)
            else:
                raise ResolvedContextError(
                    "Cannot perform operation in a failed context")
        return _check

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
            request_only: If True, only return the key from resolved packages
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
        for variant, tools in tools_dict.itervalues():
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
        for variant, tools in tools_dict.itervalues():
            for tool in tools:
                tool_sets[tool].add(variant)

        conflicts = dict((k, v) for k, v in tool_sets.iteritems() if len(v) > 1)
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
        from rez.shells import create_shell
        sh = create_shell(shell)
        executor = self._create_executor(sh, parent_environ, style=style)

        if self.load_path and os.path.isfile(self.load_path):
            executor.env.REZ_RXT_FILE = self.load_path

        self._execute(executor)
        return executor.get_output()

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

        Note that this updates os.environ and possibly sys.path.

        @param environ Environment to interpret the context within, defaults to
            os.environ if None.
        """
        interpreter = Python(target_environ=os.environ)
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)

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
        interpreter = Python(target_environ={})
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)
        return interpreter.subprocess(args, **subprocess_kwargs)

    @_on_success
    def execute_shell(self, shell=None, parent_environ=None, rcfile=None,
                      norc=False, stdin=False, command=None, quiet=False,
                      block=None, actions_callback=None, context_filepath=None,
                      start_new_session=False, detached=False, pre_command=None,
                      **Popen_args):
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
            command: If not None, execute this command in a non-interactive
                shell. Can be a list of args.
            quiet: If True, skip the welcome message in interactive shells.
            block: If True, block until the shell is terminated. If False,
                return immediately. If None, will default to blocking if the
                shell is interactive.
            actions_callback: Callback with signature (RexExecutor). This lets
                the user append custom actions to the context, such as setting
                extra environment variables.
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
        if hasattr(command, "__iter__"):
            command = shlex_join(command)

        # start a new session if specified
        if start_new_session:
            Popen_args["preexec_fn"] = os.setpgrp

        # open a separate terminal if specified
        if detached:
            term_cmd = config.terminal_emulator_command
            if term_cmd:
                term_cmd = term_cmd.strip().split()
            else:
                from rez.platform_ import platform_
                term_cmd = platform_.terminal_emulator_command
            if term_cmd:
                pre_command = term_cmd

        # block if the shell is likely to be interactive
        if block is None:
            block = not (command or stdin)

        # create the shell
        from rez.shells import create_shell
        sh = create_shell(shell)

        # context and rxt files
        tmpdir = mkdtemp_()

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
        context_code = executor.get_output()
        with open(context_file, 'w') as f:
            f.write(context_code)

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

    def to_dict(self):
        resolved_packages = []
        for pkg in (self._resolved_packages or []):
            resolved_packages.append(pkg.resource_handle.to_dict())

        patch_locks = dict((k, v.name) for k, v in self.patch_locks)

        return dict(
            serialize_version=ResolvedContext.serialize_version,

            timestamp=self.timestamp,
            requested_timestamp=self.requested_timestamp,
            building=self.building,
            caching=self.caching,
            implicit_packages=[str(x) for x in self.implicit_packages],
            package_requests=[str(x) for x in self._package_requests],
            package_paths=self.package_paths,

            default_patch_lock=self.default_patch_lock.name,
            patch_locks=patch_locks,

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
            resolved_packages=resolved_packages,
            failure_description=self.failure_description,
            graph=self.graph(as_dot=True),
            solve_time=self.solve_time,
            load_time=self.load_time)

    @classmethod
    def from_dict(cls, d):
        r = ResolvedContext.__new__(ResolvedContext)
        sz_ver = d["serialize_version"]  # for backwards compatibility
        r.load_path = None

        r.timestamp = d["timestamp"]
        r.building = d["building"]
        r.caching = d["caching"]
        r.implicit_packages = [Requirement(x) for x in d["implicit_packages"]]
        r._package_requests = [Requirement(x) for x in d["package_requests"]]
        r.package_paths = d["package_paths"]

        r.rez_version = d["rez_version"]
        r.rez_path = d["rez_path"]
        r.user = d["user"]
        r.host = d["host"]
        r.platform = d["platform"]
        r.arch = d["arch"]
        r.os = d["os"]
        r.created = d["created"]

        r.status_ = ResolverStatus[d["status"]]
        r.failure_description = d["failure_description"]
        r.solve_time = d["solve_time"]
        r.load_time = d["load_time"]

        r.graph_string = d["graph"]
        r.graph_ = None

        r._resolved_packages = []
        for d_ in d["resolved_packages"]:
            resource_handle = ResourceHandle.from_dict(d_)
            resource = resource_handle.get_resource()
            variant = Variant(resource)
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

        return r

    def _set_parent_suite(self, suite_path, context_name):
        self.parent_suite_path = suite_path
        self.suite_context_name = context_name

    def _create_executor(self, interpreter, parent_environ, style=OutputStyle.file):
        parent_vars = True if config.all_parent_variables \
            else config.parent_variables

        return RexExecutor(interpreter=interpreter,
                           output_style=style,
                           parent_environ=parent_environ,
                           parent_variables=parent_vars)

    def _get_shell_code(self, shell, parent_environ):
        # create the shell
        from rez.shells import create_shell
        sh = create_shell(shell)

        # interpret this context and write out the native context file
        executor = self._create_executor(sh, parent_environ)
        self._execute(executor)
        context_code = executor.get_output()

        return sh, context_code

    def _execute(self, executor):
        # bind various info to the execution context
        resolved_pkgs = self.resolved_packages or []
        request_str = ' '.join(str(x) for x in self._package_requests)
        implicit_str = ' '.join(str(x) for x in self.implicit_packages)
        resolve_str = ' '.join(x.qualified_package_name for x in resolved_pkgs)
        package_paths_str = os.pathsep.join(self.package_paths)

        executor.setenv("REZ_USED", self.rez_path)
        executor.setenv("REZ_USED_VERSION", self.rez_version)
        executor.setenv("REZ_USED_TIMESTAMP", str(self.timestamp))
        executor.setenv("REZ_USED_REQUESTED_TIMESTAMP",
                        str(self.requested_timestamp or 0))
        executor.setenv("REZ_USED_REQUEST", request_str)
        executor.setenv("REZ_USED_IMPLICIT_PACKAGES", implicit_str)
        executor.setenv("REZ_USED_RESOLVE", resolve_str)
        executor.setenv("REZ_USED_PACKAGES_PATH", package_paths_str)

        # rez-1 environment variables, set in backwards compatibility mode
        if config.rez_1_environment_variables and \
                not config.disable_rez_1_compatibility:
            request_str_ = " ".join([request_str, implicit_str]).strip()
            executor.setenv("REZ_VERSION", self.rez_version)
            executor.setenv("REZ_PATH", self.rez_path)
            executor.setenv("REZ_REQUEST", request_str_)
            executor.setenv("REZ_RESOLVE", resolve_str)
            executor.setenv("REZ_RAW_REQUEST", request_str_)
            executor.setenv("REZ_PACKAGES_PATH", package_paths_str)
            executor.setenv("REZ_RESOLVE_MODE", "latest")

        executor.bind('building', bool(os.getenv('REZ_BUILD_ENV')))
        executor.bind('request', RequirementsBinding(self._package_requests))
        executor.bind('implicits', RequirementsBinding(self.implicit_packages))
        executor.bind('resolve', VariantsBinding(resolved_pkgs))

        # apply each resolved package to the execution context
        for pkg in resolved_pkgs:
            executor.comment("")
            executor.comment("Commands from package %s" % pkg.qualified_name)
            executor.comment("")

            prefix = "REZ_" + pkg.name.upper().replace('.', '_')
            executor.setenv(prefix + "_VERSION", str(pkg.version))
            executor.setenv(prefix + "_BASE", pkg.base)
            executor.setenv(prefix + "_ROOT", pkg.root)

            executor.bind('this',       VariantBinding(pkg))
            executor.bind("version",    VersionBinding(pkg.version))
            executor.bind('root',       pkg.root)
            executor.bind('base',       pkg.base)

            commands = pkg.commands
            if commands:
                error_class = Exception if config.catch_rex_errors else None
                try:
                    if isinstance(commands, basestring):
                        # rex code is in a string
                        executor.execute_code(commands)
                    elif inspect.isfunction(commands):
                        # rex code is a function in a package.py
                        executor.execute_function(commands)
                except error_class as e:
                    msg = "Error in commands in file %s:\n%s" \
                          % (pkg.path, str(e))
                    raise PackageCommandError(msg)

        # append suite path if there is an active parent suite
        if self.parent_suite_path:
            tools_path = os.path.join(self.parent_suite_path, "bin")
            executor.env.PATH.append(tools_path)

        # append system paths
        executor.append_system_paths()
