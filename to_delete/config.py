"""
rez-config

rez is a tool for managing package configuration.

'package': a unit of software, or configuration information, which is
installed under a common base path, and may be available as several
variants. A specific version of software is regarded as a package - ie,
'boost' is not a package, but 'boost-1.36' is.

'package family': label for a family of versioned packages. 'boost' is a
package family, whereas 'boost-1.36' is a package.

'package base path': The path under which all variants of a package are
installed. For example, boost-1.36 and its variants might be found under
'/server/boost/1.36/'.

NOTES
---------
'Dependency transitivity' is the assumption that if a package A has a dependent
package B, then an earlier versioned A will have a dependency on an equal or
earlier version of B. For example, given the relationship:
A-3.5 dependsOn B-6.4
then we assume that:
A-3.4 dependsOn B-<=6.4

It follows that we also assume that a later version of A will have a dependency
on an equal or later version of B:
A-3.5 dependsOn B-6.4
then we assume that:
A-3.6 dependsOb B->=6.4

Examples of cases where this assumption is wrong are:
let:
A-3.5 dependsOn B-6.4
then the following cases break the assumption:
'A-3.4 dependsOn B-7.0'
'A-3.4 dependsOn B' (since 'B' is the superset of all versions of B)
'A-3.4 NOT dependsOn B'
"""

import os.path
import time
import sys
import random
import itertools
from rez.settings import settings
from rez.exceptions import *
from rez.memcached import *
from rez.packages import ResolvedPackage, PackageRangeStatement, \
    package_in_range, package_family, iter_packages_in_range
from rez.version import Version, VersionRange, VersionError

#from rez.packages import BasePackage, ResolvedPackage, split_name, \
#    package_in_range, package_family, iter_packages_in_range
#from rez.versions import ExactVersion, ExactVersionSet, Version_, VersionRange_, \
#    VersionError, to_range
#from rez.system import system
#from rez.public_enums import *
#from rez import module_root_path
#import rez.rex as rex
#import inspect
#import re


DEFAULT_ENV_SEP_MAP = {'CMAKE_MODULE_PATH': "';'"}


##############################################################################
# Public Classes
##############################################################################

class PackageRequest(object):
    """A request for a package, eg "foo-1.3+".

    Parameters
    ----------
    version_range : str, ExactVersion, ExactVersionSet, or VersionRange
            may be inexact (for eg '5.4+')
    resolve_mode : {"latest", "earliest", "none"}
            preference used when determining the order in which available versions
            are tested during the resolve.
    """
    def __init__(self, pkg_str, resolve_mode="latest", timestamp=0, paths=None):
        force_latest = pkg_str.endswith("=l")
        force_earliest = pkg_str.endswith("=e")

        if force_latest or force_earliest:
            resolve_mode = "latest" if force_latest else "earliest"
            pkg_str = pkg_str[:-2]
            self.stmt = PackageRangeStatement(pkg_str)
            pkg = package_in_range(stmt.name,
                                   stmt.range,
                                   latest=force_latest,
                                   timestamp=timestamp,
                                   paths=paths)
            if pkg is None:
                raise PkgsUnresolvedError([PackageRequest(pkg_str)])
        else:
            self.stmt = PackageRangeStatement(pkg_str)

        self.resolve_mode = resolve_mode
        self._timestamp = timestamp
        self.timestamp = timestamp

    @property
    def name(self):
        return self.stmt.name

    @property
    def version_range(self):
        return self.stmt.range

    def is_anti(self):
        return self.stmt.conflict

    def __eq__(self, other):
        return (self.stmt == other.stmt)

    def short_name(self):
        return str(self)

    def __str__(self):
        return str(self.stmt)

    """
    def __init__(self, name, version_range, resolve_mode="latest", timestamp=0):
        if isinstance(version_range, (ExactVersion, ExactVersionSet, VersionRange_)):
            self.version_range = version_range
        else:
            try:
                self.version_range = VersionRange_(version_range)
            except VersionError:
                self.version_range = ExactVersionSet(version_range)
        if self.is_weak(name):
            # convert into an anti-package
            self.version_range = self.version_range.get_inverse()
            name = anti_name(name)
        # Note: this class with have both a .version (inherited from BasePackage)
        # and a .version_range (from this class) which are both the same object.
        # The .version makes this class compatible with other BasePackage
        # functions, but the .version_range is  provided for explicitness, since
        # the version is allowed to be a range (i.e. inexact).
        BasePackage.__init__(self, name, self.version_range, timestamp)
        self.resolve_mode = resolve_mode

    def is_anti(self):
        return (self.name[0] == '!')

    @staticmethod
    def is_weak(name):
        # this is static because any weak package request will automatically be
        # converted to an anti package, so it makes no sense as an instancemethod
        return (name[0] == '~')

    def __eq__(self, other):
        return self.name == other.name and \
            self.version_range == other.version_range and \
            self.timestamp == other.timestamp and \
            self.resolve_mode == other.resolve_mode

    def __str__(self):
        return self.short_name()
    """


class PackageConflict(object):
    """
    A package conflict. This can occur between a package (possibly a specific
    variant) and a package request
    """
    def __init__(self, pkg_req_conflicting, pkg_req, variant=None):
        self.pkg_req = pkg_req
        self.pkg_req_conflicting = pkg_req_conflicting
        self.variant = variant

    def __str__(self):
        tmpstr = str(self.pkg_req)
        if self.variant:
            tmpstr +=" " + str(self.variant)
        tmpstr += " <--!--> " + str(self.pkg_req_conflicting)
        return tmpstr


##############################################################################
# Resolver
##############################################################################

class ResolveResult(object):
    request_time = None
    raw_package_requests = None
    package_requests = None
    package_resolves = None
    dot_graph = None
    failed_attempts = None
    request_timestamp = None
    resolve_time = None
    resolve_mode = None

class Resolver(object):
    """
    Where all the action happens. This class performs a package resolve.
    """
    def __init__(self,
                 resolve_mode="latest",
                 quiet=False,
                 verbosity=0,
                 max_fails=-1,
                 time_epoch=0,
                 build_requires=False,
                 assume_dt=False,
                 caching=True,
                 package_paths=None):
        """
        resolve_mode: one of: "earliest", "latest"
        quiet: if True then hides unnecessary output (such as the progress dots)
        verbosity: print extra debugging info. One of: 0, 1, 2
        max_fails: return after N failed configuration attempts, default -1 (no limit)
        time_epoch: ignore packages newer than this time-date. Default = 0 which is a special
                case, meaning do not ignore any packages
        assume_dt: Assume dependency transitivity
        caching: If True, resolve info is read from and written to a memcache daemon if possible.
        package_paths: List of paths to search for pkgs, defaults to settings.packages_path.
        """
        if not time_epoch:
            time_epoch = int(time.time())

        self.rctxt = _ResolvingContext()
        self.rctxt.resolve_mode = resolve_mode
        self.rctxt.verbosity = verbosity
        self.rctxt.max_fails = max_fails
        self.rctxt.quiet = quiet
        self.rctxt.build_requires = build_requires
        self.rctxt.assume_dt = assume_dt
        self.rctxt.time_epoch = time_epoch
        self.rctxt.caching = caching
        self.rctxt.package_paths = package_paths

        self.result = ResolveResult()
        self.result.request_time = time_epoch

    def resolve(self, pkg_reqs, no_implicit=False, meta_vars=None,
                shallow_meta_vars=None):
        """
        Perform a package resolve.
        Parameters
        ----------
        pkg_reqs: list of str or PackageRequest
                packages to resolve into a configuration
        no_implicit: bool
                whether to include the implicit packages.
        @returns
        (a) a list of ResolvedPackage objects, representing the resolved config;
        (b) a list of Commands which, when processed by a CommandInterpreter, should configure the environment;
        (c) a dot-graph representation of the config resolution, as a string;
        (d) the number of failed config attempts before the successful one was found
        -OR-
        raise the relevant exception, if config resolution is not possible
        """
        def _pkg_request(req):
            return req if isinstance(req, PackageRequest) \
                else PackageRequest(req,
                                    self.rctxt.resolve_mode,
                                    self.rctxt.time_epoch,
                                    self.rctxt.package_paths)
        """
        else str_to_pkg_req(req,
                            self.rctxt.time_epoch,
                            self.rctxt.resolve_mode,
                            self.rctxt.package_paths)
        """

        resolve_start_time = time.time()
        raw_package_requests = [_pkg_request(x) for x in pkg_reqs]

        if not no_implicit:
            to_add = []
            for pkg_str in settings.implicit_packages:
                im_pkg_req = PackageRequest(pkg_str,
                                            self.rctxt.resolve_mode,
                                            self.rctxt.time_epoch,
                                            self.rctxt.package_paths)
                """
                im_pkg_req = str_to_pkg_req(pkg_str,
                                            self.rctxt.time_epoch,
                                            self.rctxt.resolve_mode,
                                            self.rctxt.package_paths)
                """
                if im_pkg_req not in raw_package_requests:
                    to_add.append(im_pkg_req)
            self.package_requests = to_add + raw_package_requests
        else:
            self.package_requests = raw_package_requests[:]

        if self.package_requests:
            # get the resolve, possibly read/write cache
            result = self.get_cached_resolve()
            if not result:
                result = self.resolve_base()
                self.set_cached_resolve(result)

            self.result.package_resolves, self.result.dot_graph, \
                self.result.failed_attempts = result
        else:
            # special case - empty request
            self.result.package_resolves = []
            self.result.dot_graph = "digraph g{}"
            self.result.failed_attempts = 0

        resolve_end_time = time.time()
        self.result.resolve_time = resolve_end_time - resolve_start_time
        self.result.package_requests = self.package_requests
        self.result.raw_package_requests = raw_package_requests
        self.result.request_timestamp = self.rctxt.time_epoch
        self.result.resolve_mode = self.rctxt.resolve_mode
        return self.result

    def resolve_base(self):
        config = _Configuration(self.rctxt)

        for pkg_req in self.package_requests:
            config.add_package(pkg_req)

        for pkg_req in self.package_requests:
            config.add_dot_graph_verbatim('"' + str(pkg_req) + \
                '" [style=filled shape=box fillcolor="rosybrown1"] ;')
            """
            name = pkg_req.short_name()
            if name.startswith("__wrapper_"):
                name2 = name.replace("__wrapper_", "")
                config.add_dot_graph_verbatim('"' + name +
                                              '" [label="%s" style="filled" shape=folder fillcolor="rosybrown1"] ;'
                                              % (name2))
            else:
                config.add_dot_graph_verbatim('"' + name +
                                              '" [style=filled shape=box fillcolor="rosybrown1"] ;')
            """
        if (self.rctxt.verbosity != 0):
            print
            print "initial config:"
        if (self.rctxt.verbosity == 1):
            print str(config)
        elif (self.rctxt.verbosity == 2):
            config.dump()

        # do the config resolve - all the action happens here!
        pkg_res_list = config.resolve_packages()

        # color resolved packages in graph
        for pkg_res in pkg_res_list:
            config.add_dot_graph_verbatim('"' + pkg_res.short_name() +
                                          '" [style=filled fillcolor="darkseagreen1"] ;')

        if (self.rctxt.verbosity != 0):
            print
            print "final config:"
        if (self.rctxt.verbosity == 1):
            print str(config)
            print
        elif (self.rctxt.verbosity == 2):
            config.dump()
            print

        # build the dot-graph representation
        dot_graph = config.get_dot_graph_as_string()

        if get_memcache().caching_enabled():
            # here we remove unnecessary data, because if caching is on then it's gonna be sent over
            # the network, and we want to minimise traffic.
            for pkg_res in pkg_res_list:
                pkg_res.strip()

        result = (pkg_res_list,
                  dot_graph,
                  len(self.rctxt.config_fail_list))

        # we're done
        return result

    def set_cached_resolve(self, result):
        if not get_memcache().caching_enabled():
            return

        # if any local packages are involved, don't cache
        pkg_res_list = result[0]
        for pkg_res in pkg_res_list:
            if pkg_res.base.startswith(settings.local_packages_path):
                return

        get_memcache().store_resolve(settings.nonlocal_packages_path,
                                     self.package_requests, result, self.rctxt.time_epoch)

    def get_cached_resolve(self):
        # the 'cache timestamp' is the most recent timestamp of all the resolved packages. Between
        # here and rctxt.time_epoch, the resolve will be the same.
        if not get_memcache().caching_enabled():
            return None

        result, cache_timestamp = get_memcache().get_resolve(
            settings.nonlocal_packages_path, self.package_requests, self.rctxt.time_epoch)

        if not result:
            return None

        pkg_res_list = result[0]

        # discard cache if any version of any resolved pkg is also present as a local pkg,
        # unless the versions fall outside of that pkg's max bounds.
        if settings.local_packages_path in settings.packages_path:
            for pkg_res in pkg_res_list:
                fam_path = os.path.join(settings.local_packages_path, pkg_res.name)
                if os.path.isdir(fam_path):
                    # todo max bounds check
                    print_cache_warning(("Presence of local package directory %s " +
                                         "caused cache miss") % fam_path)
                    return None

        """
        # if any version of any resolved packages also appear in a local package path, and that
        # path has been modified since the cache timestamp, then discard the cached resolve.
        # TODO incorrect, time has no effect. Can only discard based on 'pkg max bounds'
        if filesys._g_local_pkgs_path in filesys._g_syspaths:
            for pkg_res in pkg_res_list:
                fam_path = os.path.join(filesys._g_local_pkgs_path, pkg_res.name)
                if os.path.isdir(fam_path):
                    path_modtime = int(os.path.getmtime(fam_path))
                    if path_modtime >= cache_timestamp:
                        print >> sys.stderr, "LOCAL package forced no cache resolve!"
                        return None
        """

        env_cmds = result[1]
        env_cmds.append("export REZ_RESOLVE_FROM_CACHE=1")
        env_cmds.append("export REZ_CACHE_TIMESTAMP=%d" % cache_timestamp)

        return result


##############################################################################
# Public Functions
##############################################################################

"""
def parse_pkg_req_str(pkg_str):
    if pkg_str.endswith("=l"):
        mode = "latest"
    elif pkg_str.endswith("=e"):
        mode = "earliest"
    else:
        mode = None
    pkg_str = pkg_str.rsplit("=", 1)[0]
    name, verrange = split_name(pkg_str)
    return name, verrange, mode

def str_to_pkg_req(pkg_str, timestamp, mode="latest", paths=None):
    name, verrange, mode_override = parse_pkg_req_str(pkg_str)
    if mode_override is not None:
        # goto filesystem and resolve version immediately
        name_ = name.lstrip('!')

        pkg = package_in_range(name_,
                               ver_range=verrange,
                               latest=(mode_override=="latest"),
                               timestamp=timestamp,
                               paths=paths)
        if pkg is None:
            raise PkgsUnresolvedError([PackageRequest(name, verrange)])

        verrange = pkg.version
        mode = mode_override
    return PackageRequest(name, verrange, mode, timestamp)
"""

def anti_name(pkg):
    """
    Return the name of the anti-package for the given package.

    pkg may be a PackageRequest, _Package, or string
    """
    if isinstance(pkg, (PackageRequest, _Package)):
        name = pkg.name
    else:
        name = pkg
    if name[0] == '!':
        raise RezError("Already an anti-package: %r" % name)
    if name[0] == '~':
        return '!' + name[1:]
    return '!' + name

def make_random_color_string():
    cols = []
    cols.append(random.randint(0, 255))
    cols.append(random.randint(0, 255))
    cols.append(random.randint(0, 255))
    if(cols[0] + cols[1] + cols[2] > 400):
        cols[random.randint(0, 2)] = random.randint(0, 100)
    s = "#"
    for c in cols:
        h = hex(c)[2:]
        if len(h) == 1:
            h = '0' + h
        s = s + h
    return s


##############################################################################
# Internal Classes
##############################################################################

class _ResolvingContext(object):
    """
    Resolving context
    """
    def __init__(self):
        self.resolve_mode = "none"
        self.verbosity = 0
        self.max_fails = -1
        self.config_fail_list = []
        self.config_uid = 0
        self.last_fail_dot_graph = None
        self.time_epoch = 0
        self.quiet = False
        self.build_requires = False
        self.assume_dt = False
        self.package_paths = None

class _PackageVariant(object):
    """
    A package variant. The 'working list' member is a list of dependencies that are
    removed during config resolution - a variant with an empty working_list is fully
    resolved. This class has been written with forward compatibility in mind - currently
    a variant is just a list of dependencies, but it may later become a dict, with
    more info than just dependencies.
    """
    def __init__(self, pkg_reqs):
        self.all_requests = tuple(pkg_reqs)
        seen = set([])
        for x in self.all_requests:
            if x.name in seen:
                raise RezError("Variants cannot contain more than one occurrance of the same package: %s" % x.name)
            seen.add(x.name)
        self.unresolved_requests = self.all_requests[:]

    def get_request(self, name):
        return dict((x.name, x) for x in self.all_requests).get(name, None)

    def remove_request(self, pkg_name):
        self.unresolved_requests = [x for x in self.unresolved_requests if x.name != pkg_name]

    def copy(self):
        var = _PackageVariant(self.all_requests)
        var.unresolved_requests = self.unresolved_requests[:]
        return var

    def __str__(self):
        return 'variant(%s)' % (', '.join([str(x) for x in self.all_requests]))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.all_requests)

class _Package(object):
    """
    Internal package representation
    """
    def __init__(self, pkg_req, rctxt):
        self.rctxt = rctxt
        self.is_transitivity = False
        self.has_added_transitivity = False
        self.base_path = None
        self.metadata = None
        self.variants = None
        self.root_path = None
        self.timestamp = None
        self.metafile = None

        # this is just caching how many vers are within pkg_req.version_range,
        # if that's >1 then we can't ever resolve this.
        self.can_resolve = None

        if pkg_req:
            self.name = pkg_req.name
            self.pkg_req = pkg_req
            self.set_version_range(pkg_req.version_range)
            if not self.is_anti() and \
                    not package_family(self.name, paths=self.rctxt.package_paths):
                raise PkgFamilyNotFoundError(self.name)
        else:
            self.name = None
            self.version_range = None
            self.pkg_req = None
            self.pkg_iter = None

    def copy(self):
        p = _Package(None, self.rctxt)
        p.is_transitivity = self.is_transitivity
        p.has_added_transitivity = self.has_added_transitivity
        p.name = self.name
        p.base_path = self.base_path
        p.root_path = self.root_path
        p.metadata = self.metadata
        p.metafile = self.metafile
        p.timestamp = self.timestamp
        p.pkg_req = self.pkg_req
        # split the iterator
        self.pkg_iter, p.pkg_iter = itertools.tee(self.pkg_iter)
        p.version_range = self.version_range

        p.variants = None
        if self.variants is not None:
            p.variants = [x.copy() for x in self.variants]
        return p

    def set_version_range(self, version_range):
        self.version_range = version_range
        # recreate the iterator.
        # NOTE: not entirely sure this is safe if iteration has already begun.
        # TODO optimisation put this of til next_request() called for first time
        self.pkg_iter = iter_packages_in_range(self.name,
                                               ver_range=self.version_range,
                                               latest=(self.pkg_req.resolve_mode=="latest"),
                                               timestamp=self.pkg_req.timestamp,
                                               paths=self.rctxt.package_paths)

    def next_request(self):
        try:
            pkg = self.pkg_iter.next()
            # NOTE: this is always an exact package. no ranges involved
            return PackageRequest("%s==%s" % (pkg.name, str(pkg.version)),
                                  self.pkg_req.resolve_mode,
                                  self.pkg_req.timestamp)
            """
            return PackageRequest(pkg.name, pkg.version,
                                  self.pkg_req.resolve_mode,
                                  self.pkg_req.timestamp)
            """
        except StopIteration:
            return None

    def get_variants(self):
        """
        Return package variants, if any
        """
        return self.variants

    def as_package_request(self):
        """
        Return this package as a package-request
        """
        return self.pkg_req

    def is_anti(self):
        """
        Return True if this is an anti-package
        """
        return (self.name[0] == '!')

    def short_name(self):
        """
        Return a short string representation, eg 'boost-1.36'
        """
        if self.version_range.is_any():
            return self.name
        else:
            return self.name + '-' + str(self.version_range)

    def is_metafile_resolved(self):
        """
        Return True if this package has had its metafile resolved
        """
        return (self.base_path != None)

    def is_resolved(self):
        """
        Return True if this package has been resolved (ie, there are either no
        variants, or a specific variant has been chosen)
        """
        return (self.root_path != None)

    def resolve(self, root_path):
        """
        Resolve this package, ie set its root path

        .. todo::
                 optimisation: just do this right at the end of resolve_packages
        """
        self.root_path = root_path

    def get_package(self, latest=True, exact=False, timestamp=0):
        return package_in_range(self.name,
                                self.version_range,
                                timestamp=timestamp,
                                latest=latest,
                                exact=exact,
                                paths=self.rctxt.package_paths)

    def resolve_metafile(self, timestamp=0):
        """
        attempt to resolve the metafile, the metadata member will be set if
        successful, and True will be returned. If the package has no variants,
        then its root-path is set and this package is regarded as fully-resolved.
        """
        if self.can_resolve is None:
            pkg_iter = iter_packages_in_range(self.name,
                                              ver_range=self.version_range,
                                              timestamp=timestamp,
                                              paths=self.rctxt.package_paths)
            try:
                pkg = pkg_iter.next()
                pkg_iter.next()
                self.can_resolve = False  # >1 pkg, won't resolve
                return False
            except StopIteration:
                pass

            self.timestamp = pkg.timestamp
            self.base_path = pkg.base
            self.metadata = pkg.metadata

            self.metafile = pkg.metafile
            metafile_variants = self.metadata['variants']
            if metafile_variants:
                # convert variants from metafile into _PackageVariants
                self.variants = []
                for metavar in metafile_variants:
                    requests = [PackageRequest(p,
                                               self.rctxt.resolve_mode,
                                               self.rctxt.time_epoch,
                                               self.rctxt.package_paths) for p in metavar]
                    """
                    requests = [str_to_pkg_req(p, self.pkg_req.timestamp,
                                               self.pkg_req.resolve_mode,
                                               self.rctxt.package_paths) for p in metavar]
                    """
                    pkg_var = _PackageVariant(requests)
                    self.variants.append(pkg_var)
            else:
                # no variants, we're fully resolved
                self.resolve(self.base_path)

            self.can_resolve = True

        return self.can_resolve

        """
        is_any = self.version_range.is_any()
        if not is_any and self.version_range.is_inexact():
            return False

        if not self.base_path:
            pkg = self.get_package(exact=True, timestamp=timestamp)
            if pkg is not None:
                self.timestamp = pkg.timestamp
                self.base_path = pkg.base
                self.metadata = pkg.metadata

                self.metafile = pkg.metafile
                metafile_variants = self.metadata['variants']
                if metafile_variants:
                    # convert variants from metafile into _PackageVariants
                    self.variants = []
                    for metavar in metafile_variants:
                        requests = [str_to_pkg_req(p, self.pkg_req.timestamp,
                                                   self.pkg_req.resolve_mode,
                                                   self.rctxt.package_paths) for p in metavar]
                        pkg_var = _PackageVariant(requests)
                        self.variants.append(pkg_var)
                else:
                    # no variants, we're fully resolved
                    self.resolve(self.base_path)

        return (self.base_path != None)
        """

    """
    def get_metadata(self, latest=True, timestamp=0):
        pkg = self.get_package(latest=latest, exact=False, timestamp=timestamp)

        if not pkg:
            return
        return pkg.metadata
    """

    def __str__(self):
        s = self.short_name()
        if self.root_path:
            s += ' @ R' + self.root_path
        elif self.base_path:
            s += ' @ B' + self.base_path
        l = [s]

        if(self.is_transitivity):
            l.append('t')

        variants = self.get_variants()
        if (variants):
            vars = []
            for var in variants:
                vars.append(var.unresolved_requests)
            l.append("working_vars:" + str(vars))
        return str(l)


class _Configuration(object):
    """
    Internal configuration representation
    """
    def __init__(self, rctxt, inc_uid=False):
        # resolving context
        self.rctxt = rctxt
        # packages map, for quick lookup
        self.pkgs = {}
        # packages list, for order retention wrt resolving
        self.families = []
        # connections in a dot graph
        self.dot_graph = []
        # uid
        if inc_uid:
            rctxt.config_uid += 1
        self.uid = rctxt.config_uid

    def get_num_packages(self):
        """
        return number of packages
        """
        num = 0
        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if not pkg.is_anti():
                num += 1
        return num

    def get_num_resolved_packages(self):
        """
        return number of resolved packages
        """
        num = 0
        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if pkg.is_resolved():
                num += 1
        return num

    def all_resolved(self):
        """
        returns True if all packages are resolved
        """
        return (self.get_num_resolved_packages() == self.get_num_packages())

    ADDPKG_CONFLICT = 0
    ADDPKG_ADD = 1
    ADDPKG_NOEFFECT = 2

    def test_pkg_req_add(self, pkg_req, create_pkg_add):
        """
        test the water to see what adding a package request would do to the config.

        Returns an ADDPKG_* constant and a _Package instance (or None).

        Possible results are:

        - (ADDPKG_CONFLICT, pkg_conflicting):
                The package cannot be added because it would conflict with
                pkg_conflicting
        - (ADDPKG_NOEFFECT, None):
                The package doesn't need to be added, there is an identical package
                already there
        - (ADDPKG_ADD, pkg_add):
                The package can be added, and the config updated accordingly by
                adding pkg_add (replacing a package with the same family name if it
                already exists in the config)

        .. note::
                that if 'create_pkg_add' is False, then 'pkg_add' will always be None.
        """
        print "test_pkg_req_add", str(pkg_req)

        # do a shortcut and test pkg short-names, if they're identical then we can often
        # return 'NOEFFECT'. Sometimes short names can mismatch, but actually be identical,
        # but this is of no real consequence, and testing on short-name is a good optimisation
        # (testing VersionRanges for equality is not trivial)
        #pkg_shortname = pkg_req.short_name()
        pkg_shortname = str(pkg_req)

        pkg_req_ver_range = pkg_req.version_range

        if pkg_req.is_anti():

            if pkg_req.name[1:] in self.pkgs:
                config_pkg = self.pkgs[pkg_req.name[1:]]

                # if anti and existing non-anti don't overlap then no effect
                ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
                if not ver_range_intersect:
                    return (_Configuration.ADDPKG_NOEFFECT, None)

                # if (inverse of anti) and non-anti intersect, then reduce existing non-anti,
                # otherwise there is a conflict
                pkg_req_inv_ver_range = pkg_req_ver_range.get_inverse()
                ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_inv_ver_range)
                if ver_range_intersect:
                    pkg_add = None
                    if create_pkg_add:
                        pkg_add = config_pkg.copy()
                        pkg_add.set_version_range(ver_range_intersect)
                        return (_Configuration.ADDPKG_ADD, pkg_add)
                else:
                    return (_Configuration.ADDPKG_CONFLICT, config_pkg)

            # union with anti if one already exists
            if pkg_req.name in self.pkgs:
                config_pkg = self.pkgs[pkg_req.name]
                if (config_pkg.short_name() == pkg_shortname):
                    return (_Configuration.ADDPKG_NOEFFECT, None)

                ver_range_union = config_pkg.version_range.get_union(pkg_req_ver_range)
                pkg_add = None
                if create_pkg_add:
                    pkg_add = config_pkg.copy()
                    pkg_add.set_version_range(ver_range_union)
                return (_Configuration.ADDPKG_ADD, pkg_add)
        else:
            try:
                # check for existing anti-package
                config_pkg = self.pkgs[anti_name(pkg_req)]
            except KeyError:
                # does not exist. move on
                pass
            else:
                # if non-anti and existing anti don't overlap then pkg can be added
                ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
                if not ver_range_intersect:
                    pkg_add = None
                    if create_pkg_add:
                        pkg_add = _Package(pkg_req, self.rctxt)
                    return (_Configuration.ADDPKG_ADD, pkg_add)

                # if non-anti and (inverse of anti) intersect, then add reduced anti,
                # otherwise there is a conflict
                config_pkg_inv_ver_range = config_pkg.version_range.get_inverse()
                ver_range_intersect = config_pkg_inv_ver_range.get_intersection(pkg_req_ver_range)
                if ver_range_intersect:
                    pkg_add = None
                    if create_pkg_add:
                        pkg_add = _Package(pkg_req, self.rctxt)
                        pkg_add.set_version_range(ver_range_intersect)
                        return (_Configuration.ADDPKG_ADD, pkg_add)
                else:
                    return (_Configuration.ADDPKG_CONFLICT, config_pkg)

            # intersect with non-anti if one already exists, and conflict if no intersection
            if pkg_req.name in self.pkgs:
                config_pkg = self.pkgs[pkg_req.name]
                if (config_pkg.short_name() == pkg_shortname):
                    return (_Configuration.ADDPKG_NOEFFECT, None)

                ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
                if ver_range_intersect:
                    pkg_add = None
                    if create_pkg_add:
                        pkg_add = config_pkg.copy()
                        pkg_add.set_version_range(ver_range_intersect)
                    return (_Configuration.ADDPKG_ADD, pkg_add)
                else:
                    return (_Configuration.ADDPKG_CONFLICT, config_pkg)

        # package can be added directly, doesn't overlap with anything
        pkg_add = None
        if create_pkg_add:
            pkg_add = _Package(pkg_req, self.rctxt)
        return (_Configuration.ADDPKG_ADD, pkg_add)

    def get_conflicting_package(self, pkg_req):
        """
        return a package in the current configuration that 'pkg' would conflict with, or
        None if no conflict would occur
        """
        result, pkg_conflict = self.test_pkg_req_add(pkg_req, False)
        if (result == _Configuration.ADDPKG_CONFLICT):
            return pkg_conflict
        else:
            return None

    PKGCONN_REDUCE = 0
    PKGCONN_RESOLVE = 1
    PKGCONN_REQUIRES = 2
    PKGCONN_CONFLICT = 3
    PKGCONN_VARIANT = 4
    PKGCONN_CYCLIC = 5
    PKGCONN_TRANSITIVE = 6

    def add_package(self, pkg_req, parent_pkg=None, dot_connection_type=0):
        """
        add a package request to this configuration, optionally describing the 'parent'
        package (ie the package that requires it), and the type of dot-graph connection,
        if the pkg has a parent pkg.
        """
        # test to see what adding this package would do
        result, pkg = self.test_pkg_req_add(pkg_req, True)

        self._add_package_to_dot_graph(pkg_req.short_name(), pkg, result,
                                       parent_pkg, dot_connection_type)

        if (result == _Configuration.ADDPKG_CONFLICT):
            pkg_conflict = PackageConflict(pkg.as_package_request(), pkg_req)
            raise PkgConflictError([pkg_conflict], self.rctxt.last_fail_dot_graph)

        elif (result == _Configuration.ADDPKG_ADD) and pkg:
            if dot_connection_type == _Configuration.PKGCONN_TRANSITIVE:
                pkg.is_transitivity = True

            # add pkg, possibly replacing existing pkg. This is to retain order of package addition,
            # since package resolution is sensitive to this
            if (not pkg.is_anti()) and (not (pkg.name in self.pkgs)):
                self.families.append(pkg.name)
            self.pkgs[pkg.name] = pkg

            # if pkg is non-anti then remove its anti from the config, if it's there. Adding a
            # non-anti pkg to the config without a conflict occurring always means we can safely
            # remove the anti pkg, if it exists.
            if not pkg.is_anti():
                if anti_name(pkg) in self.pkgs:
                    del self.pkgs[anti_name(pkg)]

    def _add_package_to_dot_graph(self, short_name, pkg, result, parent_pkg=None,
                                  dot_connection_type=0):
        if parent_pkg:
            if dot_connection_type == _Configuration.PKGCONN_TRANSITIVE:
                connt = _Configuration.PKGCONN_TRANSITIVE
                self.add_dot_graph_verbatim('"' + short_name +
                                            '" [ shape=octagon ] ;')
            else:
                connt = _Configuration.PKGCONN_REQUIRES
            self.dot_graph.append((parent_pkg.short_name(), (short_name, connt)))

        if (result == _Configuration.ADDPKG_CONFLICT):
            self.dot_graph.append((pkg.short_name(), (short_name,
                                                      _Configuration.PKGCONN_CONFLICT)))
            self.rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()

        elif (result == _Configuration.ADDPKG_ADD) and pkg:

            # update dot-graph
            pkgname = pkg.short_name()
            if pkg.name in self.pkgs:
                connt = dot_connection_type
                if (connt != _Configuration.PKGCONN_RESOLVE):
                    connt = _Configuration.PKGCONN_REDUCE

                pkgname_existing = self.pkgs[pkg.name].short_name()
                # if pkg and pkg-existing have same short-name, then a further-reduced package was already
                # in the config (eg, we added 'python' to a config with 'python-2.5')
                if (pkgname_existing == pkgname):
                    self.dot_graph.append((short_name, (pkgname_existing, connt)))
                else:
                    self.dot_graph.append((pkgname_existing, (pkgname, connt)))
            self.dot_graph.append((pkgname, None))

    def get_dot_graph_as_string(self):
        """
        return a string-representation of the dot-graph. You should be able to
        write this to file, and view it in a dot viewer, such as dotty or graphviz
        """
        dotstr = "digraph g { \n"
        conns = set()

        for connection in self.dot_graph:
            if isinstance(connection, type("")):
                verbatim_txt = connection
                dotstr += verbatim_txt + '\n'
            else:
                if connection not in conns:
                    if connection[1]:
                        dep, conntype = connection[1]
                        dotstr += '"' + connection[0] + '" -> "' + dep + '" '
                        if(conntype == _Configuration.PKGCONN_REQUIRES):
                            col = make_random_color_string()
                            conn_style = '[label=needs color="' + col + '" fontcolor="' + col + '"]'
                        elif(conntype == _Configuration.PKGCONN_TRANSITIVE):
                            col = make_random_color_string()
                            conn_style = '[label=willneed color="' + col + '" fontcolor="' + col + '"]'
                        elif(conntype == _Configuration.PKGCONN_RESOLVE):
                            conn_style = '[label=resolve color="green4" fontcolor="green4" style="bold"]'
                        elif(conntype == _Configuration.PKGCONN_REDUCE):
                            conn_style = '[label=reduce color="grey30" fontcolor="grey30" style="dashed"]'
                        elif(conntype == _Configuration.PKGCONN_VARIANT):
                            conn_style = '[label=variant color="grey30" fontcolor="grey30" style="dashed"]'
                        elif(conntype == _Configuration.PKGCONN_CYCLIC):
                            conn_style = '[label=CYCLE color="red" fontcolor="red" fontsize="30" style="bold"]'
                        else:
                            conn_style = '[label=CONFLICT color="red" fontcolor="red" fontsize="30" style="bold"]'
                        dotstr += conn_style + ' ;\n'
                    else:
                        dotstr += '"' + connection[0] + '" ;\n'
                    conns.add(connection)

        dotstr += "}\n"
        return dotstr

    def add_dot_graph_verbatim(self, txt):
        """
        add a verbatim string to the dot-graph output
        """
        self.dot_graph.append(txt)

    def copy(self):
        """
        return a shallow copy
        """
        confcopy = _Configuration(self.rctxt)
        confcopy.pkgs = self.pkgs.copy()
        confcopy.families = self.families[:]
        confcopy.dot_graph = self.dot_graph[:]
        return confcopy

    def deep_copy(self):
        confcopy = _Configuration(self.rctxt)
        confcopy.families = self.families[:]
        confcopy.dot_graph = self.dot_graph[:]

        confcopy.pkgs = {}
        for k, v in self.pkgs.iteritems():
            confcopy.pkgs[k] = v.copy()

        return confcopy

    def swap(self, a):
        """
        swap this config's contents with another
        """
        self.pkgs, a.pkgs = a.pkgs, self.pkgs
        self.families, a.families = a.families, self.families
        self.dot_graph, a.dot_graph = a.dot_graph, self.dot_graph

    def get_unresolved_packages_as_package_requests(self):
        """
        return a list of unresolved packages as package requests
        """
        pkg_reqs = []
        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if (not pkg.is_resolved()) and (not pkg.is_anti()):
                pkg_reqs.append(pkg.as_package_request())
        return pkg_reqs

    def get_all_packages_as_package_requests(self):
        """
        return a list of all packages as package requests
        """
        pkg_reqs = []
        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            pkg_reqs.append(pkg.as_package_request())
        return pkg_reqs

    def resolve_packages(self):
        """
        resolve the current configuration - all the action happens here. On
        success, a resolved package list is returned. This function should only
        fail via an exception - if an infinite loop results then there is a bug
        somewheres. Please note that the returned list order is important.
        Required packages appear first, and requirees later... since a package's
        commands may refer to env-vars set in a required package's commands.
        """

        while (not self.all_resolved()) and \
                ((self.rctxt.max_fails == -1) or (len(self.rctxt.config_fail_list) <= self.rctxt.max_fails)):

            # do an initial resolve pass
            self.resolve_packages_no_filesys()
            if self.all_resolved():
                break

            # fail if not all resolved and mode=none
            if (not self.all_resolved()) and (self.rctxt.resolve_mode == "none"):
                pkg_reqs = self.get_unresolved_packages_as_package_requests()
                raise PkgsUnresolvedError(pkg_reqs)

            # add transitive dependencies
            #self.add_transitive_dependencies()

            # this shouldn't happen here but just in case...
            if self.all_resolved():
                break

            # find first package with unresolved metafile. Note that self.families exists in
            # order to retain package order, because different package order can result
            # in different configuration resolution.
            pkg = None
            for name in self.families:
                pkg_ = self.pkgs[name]
                if not pkg_.is_metafile_resolved():
                    pkg = pkg_
                    break

            if not pkg:
                # The remaining unresolved packages must have more than one variant each. So
                # find that variant, out of all remaining packages, that is 'least suitable',
                # and remove it. 'least suitable' means that the variant has largest number
                # of packages that do not intersect with anything in the config.
                if (self.rctxt.verbosity != 0):
                    print
                    print "Ran out of concrete resolution choices, yet unresolved packages still remain:"
                    if (self.rctxt.verbosity == 1):
                        print str(self)
                    elif (self.rctxt.verbosity == 2):
                        self.dump()

                self.remove_least_suitable_variant()

            else:
                valid_config_found = False

                # attempt to resolve a copy of the current config with this package resolved
                # as closely as possible to desired (eg in mode=latest, start with latest and
                # work down). The first config to resolve represents the most desirable. Note
                # that resolve_packages will be called recursively
                num_version_searches = 0
                while ((self.rctxt.max_fails == -1) or
                      (len(self.rctxt.config_fail_list) <= self.rctxt.max_fails)):

                    num_version_searches += 1

                    # resolve package to as closely desired as possible
                    pkg_req_ = pkg.next_request()
                    if pkg_req_ is None:
                        # FIXME: don't have easy access to the sub-version-range that we failed on
                        if(num_version_searches == 1):
#                             # this means that rather than running out of versions of this lib to try, there
#                             # were never any versions found at all - which means this package doesn't exist
#                             self.add_dot_graph_verbatim('"' +
#                                 pkg_req_.short_name() + ' NOT FOUND' +
#                                 '" [style=filled fillcolor="orangered"] ;')
#                             self.add_dot_graph_verbatim('"' +
#                                 pkg_req_.short_name() + '" -> "' +
#                                 pkg_req_.short_name() + ' NOT FOUND" ;')
#                             self.rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()
#                             sys.stderr.write("Warning! Package not found: " + str(pkg_req_) + "\n")
                            raise PkgNotFoundError(pkg.as_package_request())

                        if (self.uid == 0):
                            # we're the topmost configuration, and there are no more packages to try -
                            # all possible configuration attempts have failed at this point
                            break
                        else:
                            raise PkgsUnresolvedError([pkg.as_package_request()])

                    pkg_resolve_str = pkg.short_name() + " --> " + pkg_req_.short_name()

                    # create config copy, bit of fiddling though cause we want a proper guid
                    config2 = _Configuration(self.rctxt, inc_uid=True)
                    config2 = self.deep_copy()
                    config2.uid = config2.uid

                    if (self.rctxt.verbosity != 0):
                        print
                        print "SPAWNED NEW CONFIG #" + str(config2.uid) + " FROM PARENT #" + str(self.uid) + \
                            " BASED ON FILESYS RESOLUTION: " + pkg_resolve_str

                    # attempt to add package to config copy
                    try:
                        config2.add_package(pkg_req_, None, _Configuration.PKGCONN_RESOLVE)
                    except PkgConflictError, e:
                        self.rctxt.last_fail_dot_graph = config2.get_dot_graph_as_string()

                        if (self.rctxt.verbosity != 0):
                            print
                            print "CONFIG #" + str(config2.uid) + " FAILED (" + e.__class__.__name__ + "):"
                            print str(e)
                            print
                            print "ROLLING BACK TO CONFIG #" + self.uid
                        continue

                    if (self.rctxt.verbosity):
                        print
                        print "config after applying: " + pkg_resolve_str
                        if (self.rctxt.verbosity == 1):
                            print str(config2)
                        elif (self.rctxt.verbosity == 2):
                            config2.dump()

                    # now fully resolve config copy
                    try:
                        config2.resolve_packages()
                    except (
                            PkgConfigNotResolvedError,
                            PkgsUnresolvedError,
                            PkgConflictError,
                            PkgNotFoundError,
                            PkgFamilyNotFoundError,
                            PkgSystemError), e:

                        # store fail reason into list, unless it's a PkgConfigNotResolvedError - this error just
                        # tells us that the sub-config failed because its sub-config failed.
                        if (type(e) not in [PkgConfigNotResolvedError, PkgsUnresolvedError]):

                            sys.stderr.write("conflict " + str(len(self.rctxt.config_fail_list)) +
                                             ": " + config2.short_str() + '\n')
                            sys.stderr.flush()

                            this_fail = "config: (" + str(config2).strip() + "): " + \
                                e.__class__.__name__ + ": " + str(e)

                            if(self.rctxt.max_fails >= 0):
                                if(len(self.rctxt.config_fail_list) <= self.rctxt.max_fails):
                                    self.rctxt.config_fail_list.append(this_fail)
                                    if(len(self.rctxt.config_fail_list) > self.rctxt.max_fails):
                                        self.rctxt.config_fail_list.append(
                                            "Maximum configuration failures reached.")
                                        pkg_reqs_ = self.get_all_packages_as_package_requests()
                                        raise PkgConfigNotResolvedError(pkg_reqs_,
                                                                        self.rctxt.config_fail_list, self.rctxt.last_fail_dot_graph)
                            else:
                                self.rctxt.config_fail_list.append(this_fail)

                        if (self.rctxt.verbosity != 0):
                            print
                            print "CONFIG #" + str(config2.uid) + " FAILED (" + e.__class__.__name__ + "):"
                            print str(e)
                            print
                            print "ROLLING BACK TO CONFIG #" + str(self.uid)

                        continue

                    # if we got here then we have a valid config yay!
                    self.swap(config2)
                    valid_config_found = True
                    break

                if not valid_config_found:
                    # we're exhausted the possible versions of this package to try
                    fail_msg = "No more versions to be found on filesys: " + pkg.short_name()
                    if (self.rctxt.verbosity != 0):
                        print
                        print fail_msg

                    pkg_reqs_ = self.get_all_packages_as_package_requests()
                    raise PkgConfigNotResolvedError(pkg_reqs_,
                                                    self.rctxt.config_fail_list, self.rctxt.last_fail_dot_graph)

        #################################################
        # woohoo, we have a fully resolved configuration!
        #################################################

        # check for cyclic dependencies
        cyclic_deps = self.detect_cyclic_dependencies()
        if len(cyclic_deps) > 0:
            # highlight cycles in the dot-graph
            for pkg1, pkg2 in cyclic_deps:
                self.dot_graph.append((pkg1, (pkg2, _Configuration.PKGCONN_CYCLIC)))

            dot_str = self.get_dot_graph_as_string()
            raise PkgCyclicDependency(cyclic_deps, dot_str)

        # convert packages into a list of package resolutions, forcing them into the correct
        # order wrt command sourcing
        ordered_fams = self.get_ordered_families()

        pkg_ress = []
        for name in ordered_fams:
            pkg = self.pkgs[name]
            if not pkg.is_anti():
                # HACK - get version from version_range
                version = Version(str(pkg.version_range).replace("==",""))
                pkg_res = ResolvedPackage(name,
                                          version,
                                          pkg.metafile, pkg.timestamp,
                                          pkg.metadata, pkg.base_path,
                                          pkg.root_path)
                pkg_ress.append(pkg_res)

        return pkg_ress

    def _create_family_dependency_tree(self):
        """
        From the dot-graph, extract a dependency tree containing unversioned pkgs (ie families),
        and a set of all existing families
        """
        deps = set()
        fams = set()
        for conn in self.dot_graph:
            if (not isinstance(conn, type(""))) and \
                    (conn[0][0] != '!'):
                fam1 = conn[0].split('-', 1)[0]
                fams.add(fam1)
                if (conn[1] != None) and \
                        (conn[1][1] == _Configuration.PKGCONN_REQUIRES) and \
                        (conn[1][0][0] != '!'):
                    fam2 = conn[1][0].split('-', 1)[0]
                    fams.add(fam2)
                    if fam1 != fam2:
                        deps.add((fam1, fam2))

        return deps, fams

    def get_ordered_families(self):
        """
        Return the families of all packages in such an order that required packages appear
        before requirees. This means we can properly order package command construction -
        if A requires B, then A's commands might refer to an env-var set in B's commands.
        """
        fam_list = []
        deps, fams = self._create_family_dependency_tree()

        while len(deps) > 0:
            parents = set()
            children = set()
            for dep in deps:
                parents.add(dep[0])
                children.add(dep[1])

            leaf_fams = children - parents
            if len(leaf_fams) == 0:
                break 	# if we hit this then there are cycle(s) somewhere

            for fam in leaf_fams:
                fam_list.append(fam)

            del_deps = set()
            for dep in deps:
                if dep[1] in leaf_fams:
                    del_deps.add(dep)
            deps -= del_deps

            fams -= leaf_fams

        # anything left in the fam set is a topmost node
        for fam in fams:
            fam_list.append(fam)

        return fam_list

    def detect_cyclic_dependencies(self):
        """
        detect cyclic dependencies, if they exist
        """
        # extract dependency tree from dot-graph
        deps = self._create_family_dependency_tree()[0]

        # remove leaf nodes
        while len(deps) > 0:
            parents = set()
            children = set()
            for dep in deps:
                parents.add(dep[0])
                children.add(dep[1])

            leaf_fams = children - parents
            if len(leaf_fams) == 0:
                break

            del_deps = set()
            for dep in deps:
                if dep[1] in leaf_fams:
                    del_deps.add(dep)
            deps -= del_deps

        # remove topmost nodes
        while len(deps) > 0:
            parents = set()
            children = set()
            for dep in deps:
                parents.add(dep[0])
                children.add(dep[1])

            top_fams = parents - children
            if len(top_fams) == 0:
                break

            del_deps = set()
            for dep in deps:
                if dep[0] in top_fams:
                    del_deps.add(dep)
            deps -= del_deps

        # anything left is part of a cyclic loop...

        if len(deps) > 0:
            # inject pkg versions into deps list
            deps2 = set()
            for dep in deps:
                pkg1 = self.pkgs[dep[0]].short_name()
                pkg2 = self.pkgs[dep[1]].short_name()
                deps2.add((pkg1, pkg2))
            deps = deps2

        return deps

    def resolve_packages_no_filesys(self):
        """
        resolve current packages as far as possible without querying the file system
        """

        nresolved_metafiles = -1
        nresolved_common_variant_pkgs = -1
        nconflicting_variants_removed = -1
        nresolved_single_variant_pkgs = -1

        while (((
            nresolved_metafiles +
            nresolved_common_variant_pkgs +
            nconflicting_variants_removed +
            nresolved_single_variant_pkgs) != 0) and
                (not self.all_resolved())):

            # resolve metafiles
            nresolved_metafiles = self.resolve_metafiles()

            # remove conflicting variants
            nconflicting_variants_removed = self.remove_conflicting_variants()

            # resolve common variant packages
            nresolved_common_variant_pkgs = self.resolve_common_variants()

            # resolve packages with a single, fully-resolved variant
            nresolved_single_variant_pkgs = self.resolve_single_variant_packages()

    def remove_least_suitable_variant(self):
        """
        remove one variant from any remaining unresolved packages, such that that variant is
        'least suitable' - that is, has the greatest number of packages which do not appear
        in the current configuration
        TODO remove this I think, error instead
        """

        bad_pkg = None
        bad_variant = None
        bad_variant_score = -1

        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if (not pkg.is_resolved()) and (not pkg.is_anti()):
                for variant in pkg.get_variants():
                    sc = self.get_num_unknown_pkgs(variant.unresolved_requests)
                    if (sc > bad_variant_score):
                        bad_pkg = pkg
                        bad_variant = variant
                        bad_variant_score = sc

        bad_pkg.get_variants().remove(bad_variant)

        if (self.rctxt.verbosity != 0):
            print
            print "removed least suitable variant:"
            print bad_pkg.short_name() + " variant:" + str(bad_variant)

    def get_num_unknown_pkgs(self, pkg_reqs):
        """
        given a list of package requests, return the number of packages in the list
        which do not appear in the current configuration
        """
        return len([pkg_req for pkg_req in pkg_reqs if pkg_req.name not in self.pkgs])

    def resolve_metafiles(self):
        """
        for each package, resolve metafiles until no more can be resolved, returning
        the number of metafiles that were resolved.
        """
        num = 0
        config2 = None

        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if (pkg.metadata == None):
                if pkg.resolve_metafile(self.rctxt.time_epoch):
                    num += 1

                    if (self.rctxt.verbosity):
                        print
                        print "resolved metafile for " + pkg.short_name() + ":"
                        print str(pkg)

                    # add required packages to the configuration, this may
                    # reduce wrt existing packages (eg: foo-1 -> foo-1.2 is a reduction)
                    if self.rctxt.build_requires:
                        requires = (pkg.metadata['build_requires'] or []) + (pkg.metadata['requires'] or [])
                    else:
                        requires = pkg.metadata['requires']

                    if requires:
                        for pkg_str in requires:
                            pkg_req = PackageRequest(pkg_str,
                                                     self.rctxt.resolve_mode,
                                                     self.rctxt.time_epoch,
                                                     self.rctxt.package_paths)
                            """
                            pkg_req = str_to_pkg_req(pkg_str,
                                                     self.rctxt.time_epoch,
                                                     self.rctxt.resolve_mode,
                                                     self.rctxt.package_paths)
                            """

                            if (self.rctxt.verbosity != 0):
                                print
                                print "adding " + pkg.short_name() + \
                                    "'s required package " + pkg_req.short_name() + '...'

                            if not config2:
                                config2 = self.copy()
                            config2.add_package(pkg_req, pkg)

                            if (self.rctxt.verbosity != 0):
                                print "config after adding " + pkg.short_name() + \
                                    "'s required package " + pkg_req.short_name() + ':'
                            if (self.rctxt.verbosity == 1):
                                print str(config2)
                            elif (self.rctxt.verbosity >= 2):
                                config2.dump()

        if config2:
            self.swap(config2)
        return num

    """
    def add_transitive_dependencies(self):
        if not self.rctxt.assume_dt:
            return
        while (self._add_transitive_dependencies() > 0):
            pass

    def _add_transitive_dependencies(self):
        num = 0
        config2 = None

        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if pkg.is_metafile_resolved():
                continue
            if pkg.is_anti():
                continue
            if pkg.has_added_transitivity:
                continue

            # get the requires lists for the earliest and latest versions of this pkg
            # TODO this is crap, we could take a more refined approach to this. V2.
            metafile_e = pkg.get_metadata(latest=False, timestamp=self.rctxt.time_epoch)
            if not metafile_e:
                continue

            metafile_l = pkg.get_metadata(latest=True, timestamp=self.rctxt.time_epoch)
            if not metafile_l:
                continue

            pkg.has_added_transitivity = True

            requires_e = metafile_e['requires']
            requires_l = metafile_l['requires']
            if (not requires_e) or (not requires_l):
                continue

            # find pkgs that exist in the requires of both, and add these to the current
            # config as 'transitivity' packages
            for pkg_str_e in requires_e:
                if (pkg_str_e[0] == '!') or (pkg_str_e[0] == '~'):
                    continue

                pkg_req_e = str_to_pkg_req(pkg_str_e,
                                           self.rctxt.time_epoch,
                                           self.rctxt.resolve_mode,
                                           self.rctxt.package_paths)

                for pkg_str_l in requires_l:
                    pkg_req_l = str_to_pkg_req(pkg_str_l,
                                               self.rctxt.time_epoch,
                                               self.rctxt.resolve_mode,
                                               self.rctxt.package_paths)
                    if (pkg_req_e.name == pkg_req_l.name):
                        pkg_req = pkg_req_e
                        if (pkg_req_e.version_range != pkg_req_l.version_range):
                            # calc version range
                            # FIXME: big assumption here that these ranges can be Versions (will break for e.g. '1.0|2.0'):
                            v_e = Version_(str(pkg_req_e.version_range))
                            v_l = Version_(str(pkg_req_l.version_range))
                            if(not v_e.ge < v_l.lt):
                                continue
                            v = v_e.get_span(v_l)
                            # TODO: test this alternate code:
# 							v_union = pkg_req_e.version_range.get_union(pkg_req_l.version_range)
# 							v = v_union.get_span()

                            pkg_req = PackageRequest(pkg_req_e.name, v,
                                                     self.rctxt.resolve_mode,
                                                     self.rctxt.time_epoch)

                        if not config2:
                            config2 = self.copy()
                        config2.add_package(pkg_req, pkg, _Configuration.PKGCONN_TRANSITIVE)
                        num = num + 1

            # find common variants that exist in both. Note that this code is somewhat redundant,
            # v similar work is done in resolve_common_variants - fix this in rez V2
            variants_e = metafile_e['variants']
            variants_l = metafile_l['variants']
            if (not variants_e) or (not variants_l):
                continue

            common_pkg_fams = None
            pkg_vers = defaultdict(list)

            for variant in (variants_e + variants_l):
                comm_fams = set()
                for pkgstr in variant:
                    pkgreq = str_to_pkg_req(pkgstr,
                                            self.rctxt.time_epoch,
                                            self.rctxt.resolve_mode,
                                            self.rctxt.package_paths)
                    comm_fams.add(pkgreq.name)
                    pkg_vers[pkgreq.name].append(pkgreq.version_range)

                if (common_pkg_fams == None):
                    common_pkg_fams = comm_fams
                else:
                    common_pkg_fams &= comm_fams

                if len(common_pkg_fams) == 0:
                    break

            if (common_pkg_fams != None):
                for pkg_fam in common_pkg_fams:
                    versions = pkg_vers[pkg_fam]
                    ver_range = to_range(versions)

                    v = ver_range.get_span()
                    if v:
                        pkg_req = PackageRequest(pkg_fam, v,
                                                 self.rctxt.resolve_mode,
                                                 self.rctxt.time_epoch)

                        if not config2:
                            config2 = self.copy()
                        config2.add_package(pkg_req, pkg, _Configuration.PKGCONN_TRANSITIVE)
                        num = num + 1

        if config2:
            self.swap(config2)
        return num
    """

    def remove_conflicting_variants(self):
        """
        for each package, remove those variants which contain one or more packages which
        conflict with the current configuration. If a package has all of its variants
        removed in this way, then a pkg-conflict exception will be raised.
        """
        if (self.rctxt.verbosity >= 2):
            print
            print "removing conflicting variants..."

        num = 0

        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():

            variants = pkg.get_variants()
            if variants != None:
                conflicts = []

                conflicting_variants = set()
                for variant in variants:
                    for pkg_req_ in variant.all_requests:
                        pkg_conflicting = self.get_conflicting_package(pkg_req_)
                        if pkg_conflicting:
                            pkg_req_conflicting = pkg_conflicting.as_package_request()
                            pkg_req_this = pkg.as_package_request()
                            pc = PackageConflict(pkg_req_conflicting, pkg_req_this, variant)
                            conflicts.append(pc)
                            conflicting_variants.add(variant)
                            num += 1
                            break

                if (len(conflicts) > 0):
                    if (len(conflicts) == len(variants)):  # all variants conflict

                        self.add_dot_graph_verbatim(
                            'subgraph cluster_variants {\n' +
                            'style=filled ;\n' +
                            'label=variants ;\n' +
                            'fillcolor="lightcyan1" ;')

                        # show all variants and conflicts in dot-graph
                        for variant in variants:
                            varstr = ", ".join([x.short_name() for x in variant.all_requests])
                            self.add_dot_graph_verbatim('"' + varstr + '" [style=filled fillcolor="white"] ;')

                        self.add_dot_graph_verbatim('}')

                        for variant in variants:
                            varstr = ", ".join([x.short_name() for x in variant.all_requests])
                            self.dot_graph.append((pkg_req_this.short_name(),
                                                 (varstr, _Configuration.PKGCONN_VARIANT)))
                            self.dot_graph.append((pkg_req_conflicting.short_name(),
                                                 (varstr, _Configuration.PKGCONN_CONFLICT)))

                        self.rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()
                        raise PkgConflictError(conflicts)
                    else:
                        for cv in conflicting_variants:
                            variants.remove(cv)

                        if (self.rctxt.verbosity >= 2):
                            print
                            print "removed conflicting variants from " + pkg.short_name() + ':'
                            for conflict in conflicts:
                                print str(conflict)
        return num

    def resolve_common_variants(self):
        """
        for each package, find common package families within its variants, and
        add these to the configuration. For eg, if a pkg has 2 variants
        'python-2.5' and 'python-2.6', then the inexact package 'python-2.5|2.6'
        will be added to the configuration (but only if ALL variants reference a
        'python' package). Return the number of common package families
        resolved. Note that if a package contains a single variant, this this
        function will add every package in the variant to the configuration.
        """
        num = 0
        config2 = self.copy()

        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():

            variants = pkg.get_variants()
            if variants != None:

                # find common package families
                common_pkgnames = None
                for variant in variants:
                    if variant.unresolved_requests:
                        pkgnames = [p.name for p in variant.unresolved_requests]
                        if common_pkgnames is None:
                            common_pkgnames = set(pkgnames)
                        else:
                            common_pkgnames.intersection_update(pkgnames)

                if common_pkgnames:
                    num += len(common_pkgnames)

                    # add the union of each common package to the configuration,
                    # and remove the packages from the variants' working lists
                    for common_pkgname in common_pkgnames:
                        version_range = None
                        for variant in variants:
                            this_range = variant.get_request(common_pkgname).version_range
                            if version_range is None:
                                version_range = this_range
                            else:
                                version_range = version_range.get_union(this_range)

                        pkg_req_ = PackageRequest(common_pkgname, version_range)
                        config2.add_package(pkg_req_, pkg)

                        for variant in variants:
                            variant.remove_request(common_pkgname)

                        if (self.rctxt.verbosity != 0):
                            print
                            print ("removed common package family '" +
                                   common_pkgname + "' from " +
                                   pkg.short_name() + "'s variants; config after adding " +
                                   pkg_req_.short_name() + ':')
                        if (self.rctxt.verbosity == 1):
                            print str(config2)
                        elif (self.rctxt.verbosity >= 2):
                            config2.dump()

        self.swap(config2)
        return num

    def resolve_single_variant_packages(self):
        """
        find packages which have one non-conflicting, fully-resolved variant. These
        packages can now be fully resolved
        """

        num = 0
        # FIXME: if order matters here, we should not be using a dictionary
        for pkg in self.pkgs.itervalues():
            if pkg.is_resolved():
                continue

            variants = pkg.get_variants()
            if (variants != None) and (len(variants) == 1):
                variant = variants[0]
                if (len(variant.unresolved_requests) == 0):

                    # check resolved path exists
                    root_path = os.path.join(pkg.base_path, *[x.short_name() for x in variant.all_requests])
                    if not os.path.isdir(root_path):
                        pkg_req_ = pkg.as_package_request()

                        self.add_dot_graph_verbatim('"' +
                                                    pkg_req_.short_name() + ' NOT FOUND' +
                                                    '" [style=filled fillcolor="orangered"] ;')
                        self.add_dot_graph_verbatim('"' +
                                                    pkg_req_.short_name() + '" -> "' +
                                                    pkg_req_.short_name() + ' NOT FOUND" ;')
                        self.rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()

                        print >> sys.stderr, "Warning! Package body of %s not found at %s" \
                                             % (str(pkg_req_), root_path)
                        raise PkgNotFoundError(pkg_req_, root_path)

                    pkg.resolve(root_path)
                    num += 1

                    if (self.rctxt.verbosity != 0):
                        print
                        print "resolved single-variant package " + pkg.short_name() + ':'
                    if (self.rctxt.verbosity == 1):
                        print str(self)
                    elif (self.rctxt.verbosity >= 2):
                        print str(pkg)
        return num

    def dump(self):
        """
        debug printout
        """
        for name in self.families:
            pkg = self.pkgs[name]
            if (pkg.metadata == None):
                print pkg.short_name()
            else:
                print str(pkg)

    def __str__(self):
        """
        short printout
        """
        str_ = ""
        for name in self.families:
            pkg = self.pkgs[name]
            str_ += pkg.short_name()

            modif = "("
            if pkg.is_resolved():
                modif += "r"
            elif pkg.is_metafile_resolved():
                modif += "b"
            else:
                modif += "u"
            if pkg.is_transitivity:
                modif += "t"
            str_ += modif + ") "

        return str_

    def short_str(self):
        """
        even shorter printout
        """
        str_ = ""
        for name in self.families:
            pkg = self.pkgs[name]
            str_ += pkg.short_name() + " "
        return str_



#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
