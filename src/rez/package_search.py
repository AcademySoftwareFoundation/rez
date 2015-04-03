"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""


from rez.packages_ import iter_package_families, iter_packages, get_latest_package
from rez.exceptions import PackageFamilyNotFoundError
from rez.util import ProgressBar
from rez.vendor.pygraph.classes.digraph import digraph
from collections import defaultdict
from rez.utils.formatting import PackageRequest


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
    it = iter_package_families(paths)
    package_names = set(x.name for x in it)
    if package_name not in package_names:
        raise PackageFamilyNotFoundError("No such package family %r" % package_name)

    if depth == 0:
        return pkgs_list, g

    bar = ProgressBar("Searching", len(package_names))
    lookup = defaultdict(set)

    for i, package_name_ in enumerate(package_names):
        bar.next()
        it = iter_packages(name=package_name_, paths=paths)
        pkg = max(it, key=lambda x: x.version)

        requires = set(pkg.requires or [])
        for req_list in (pkg.variants or []):
            requires.update(req_list)

        for req in requires:
            if not req.conflict:
                lookup[req.name].add(package_name_)

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
            working_set_.update(parents)
            consumed.update(parents)

            for parent in parents:
                g.add_node(parent, attrs=node_attrs)
                g.add_edge((parent, child))

        if working_set_:
            pkgs_list.append(sorted(list(working_set_)))

        working_set = working_set_
        n += 1

    return pkgs_list, g


def get_plugins(package_name, paths=None):
    """Find packages that are plugins of the given package.

    Args:
        package_name (str): Name of the package.
        paths (list of str): Paths to search for packages, defaults to
            `config.packages_path`.

    Returns:
        list of str: The packages that are plugins of the given package.
    """
    pkg = get_latest_package(package_name, paths=paths, error=True)
    if not pkg.has_plugins:
        return []

    it = iter_package_families(paths)
    package_names = set(x.name for x in it)
    bar = ProgressBar("Searching", len(package_names))

    plugin_pkgs = []
    for package_name_ in package_names:
        bar.next()
        if package_name_ == package_name:
            continue  # not a plugin of itself

        plugin_pkg = get_latest_package(package_name_, paths=paths)
        if not plugin_pkg.plugin_for:
            continue
        for plugin_for in plugin_pkg.plugin_for:
            if plugin_for == pkg.name:
                plugin_pkgs.append(package_name_)

    bar.finish()
    return plugin_pkgs
