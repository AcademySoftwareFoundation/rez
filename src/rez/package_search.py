"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""

import os
import pickle
import time

from rez.config import config
from rez.packages import iter_package_families, iter_packages
from rez.exceptions import PackageRequestError
from rez.util import ProgressBar
from rez.vendor.pygraph.classes.digraph import digraph
#from rez.vendor.progress.bar import Bar
from collections import defaultdict


def _get_cache_reverse_lookup(max_time_interval=10):

    """Try to returns a previously cached lookup dictionary

    max_time_interval:
        measured in minutes, to determine whether the cache is out-dated, i.e. c_time - cache_file.st_mtime <= max_time_interval
        default value is 10 (minutes)

    Returns:
        defaultdict
    """

    cache_path = '/tmp/rez_reverse_lookup.dat'
    if os.path.exists(cache_path):
        if (time.time() - os.stat(cache_path).st_mtime) / 60 >= max_time_interval:
            return None
        with open(cache_path, 'r') as fh:
            return pickle.load(fh)
    return None


def _save_reverse_lookup(lookup):

    """Saves reverse lookup dictionary"""

    with open('/tmp/rez_reverse_lookup.dat', 'w') as fh:
        pickle.dump(lookup, fh)


def get_reverse_dependency_tree(package_name, depth=None, paths=None):
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

    lookup = _get_cache_reverse_lookup()
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
