"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""
from rez.packages import iter_package_families, iter_packages
from rez.exceptions import PackageRequestError
from rez.util import ProgressBar
from rez.vendor.pygraph.classes.digraph import digraph
from collections import defaultdict

import os
import sys
import pickle
import time



REVERSE_FAMILY_DEPENDENCIES_CACHE = '/tmp/rez_reverse_lookup.dat'
MINUTES_BEFORE_CACHE_EXPIRY = 10


def _get_cached_reverse_lookup(minutes_before_cache_expiry=MINUTES_BEFORE_CACHE_EXPIRY):

    """Try to returns a previously cached lookup dictionary

    minutes_before_cache_expiry:
        measured in minutes, to determine whether the cache is out-dated,
        i.e. c_time - cache_file.st_mtime <= minutes_before_cache_expiry
        default value is 10 (minutes)
        * the caller may pass in a negative value to force-update the cache

    Returns:
        defaultdict
    """

    if not os.path.exists(REVERSE_FAMILY_DEPENDENCIES_CACHE):
        return None
    if not os.access(REVERSE_FAMILY_DEPENDENCIES_CACHE, os.R_OK):
        sys.stderr.write('\nYou do not have enough permission to read the cache: %s\n' % REVERSE_FAMILY_DEPENDENCIES_CACHE)
        return None
    if (time.time() - os.stat(REVERSE_FAMILY_DEPENDENCIES_CACHE).st_mtime) / 60 >= minutes_before_cache_expiry:
        return None
    with open(REVERSE_FAMILY_DEPENDENCIES_CACHE, 'r') as fh:
        return pickle.load(fh)


def _save_reverse_lookup(lookup):

    """Saves reverse lookup dictionary"""

    with open(REVERSE_FAMILY_DEPENDENCIES_CACHE, 'w') as fh:
        pickle.dump(lookup, fh)


def get_reverse_dependency_tree(package_name, depth=None, paths=None, force_update_cache=False):
    """Find packages that depend on the given package.

    This is a reverse dependency lookup. A tree is constructed, showing what
    packages depend on the given package, with an optional depth limit. A
    resolve does not occur. Only the latest version of each package is used,
    and requirements from all variants of that package are used.

    Args:
        package_name (str): Name of the package depended on.
        depth (int): Tree depth limit, unlimited if None.
        paths (list of str): paths to search for packages, defaults to
            `config.packages_path`.
        force_update_cache: whether to force-update the local cache file that stores the reverse family dependencies.
                            by default this cache is updated every 10 minutes.

    Returns:
        A 2-tuple:
        - (list of list of str): Lists of package names, where each list is a
          single depth in the tree. The first list is always [`package_name`].
        - `pygraph.digraph` object, where nodes are package names, and
          `package_name` is always the leaf node.
    """
    pkgs_list = [[package_name]]
    g = digraph()
    g.add_node(package_name)

    # build reverse lookup
    fams = list(iter_package_families(paths))

    package_names = set(x.name for x in fams)
    if package_name not in package_names:
        raise PackageRequestError("No such package family %r" % package_name)

    if depth == 0:
        return pkgs_list, g

    nfams = len(fams)
    #bar = Bar("Searching", max=nfams, bar_prefix=' [', bar_suffix='] ')
    bar = ProgressBar("Searching", nfams)

    lookup = _get_cached_reverse_lookup(minutes_before_cache_expiry=-1 if force_update_cache else MINUTES_BEFORE_CACHE_EXPIRY)
    if not lookup:
        lookup = defaultdict(set)

        for i, fam in enumerate(fams):
            bar.next()
            it = iter_packages(name=fam.name, paths=paths)
            try:
                pkg = max(it, key=lambda x: x.version)
            except ValueError:
                continue

            requires = set(pkg.requires or [])
            for req_list in (pkg.variants or []):
                requires |= set(req_list)

            for req in requires:
                if not req.conflict:
                    lookup[req.name].add(fam.name)

        _save_reverse_lookup(lookup)

    # perform traversal
    bar.finish()
    n = 0
    consumed = set([package_name])
    working_set = set([package_name])

    node_color = "#F6F6F6"
    node_fontsize = 10
    node_attrs = [("fillcolor", node_color),
                  ("style", "filled"),
                  ("fontsize", node_fontsize)]

    while working_set and (depth is None or n < depth):
        working_set_ = set()

        for child in working_set:
            parents = lookup[child] - consumed
            working_set_ |= parents
            consumed |= parents

            for parent in parents:
                g.add_node(parent, attrs=node_attrs)
                g.add_edge((parent, child))

        if working_set_:
            pkgs_list.append(list(working_set_))

        working_set = working_set_
        n += 1

    return pkgs_list, g, lookup
