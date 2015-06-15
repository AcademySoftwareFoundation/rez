"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""

import os
import fnmatch

from rez.packages_ import iter_package_families, iter_packages, get_latest_package
from rez.exceptions import PackageFamilyNotFoundError
from rez.util import ProgressBar
from rez.utils.logging_ import print_error
from rez.vendor.pygraph.classes.digraph import digraph
from collections import defaultdict
from rez.utils.formatting import get_epoch_time_from_str,  expand_abbreviations

from rez.config import config

from rez.vendor.version.requirement import Requirement
from rez.exceptions import RezError

# these are package fields that can be printed using the --format option.
# It's a hardcoded list because some fields, even though they can be printed,
# aren't very useful to see here.
fields = sorted((
    'pre_commands', 'tools', 'uuid', 'build_requires', 'version', 'timestamp',
    'release_message', 'private_build_requires', 'revision', 'description',
    'base', 'authors', 'variants', 'commands', 'name', 'changelog',
    'post_commands', 'requires', 'root', 'index', 'uri', 'num_variants',
    'qualified_name'))


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

def resource_search(resources_request, package_paths=None, resource_type="auto", no_local=False,
                    latest=False, after_time=0, before_time=0, validate= False, output_format=None,sort_results=False,
                    search_for_errors=False, suppress_warning=False, suppress_new_lines=False, debug=False):
    """
    Search resource information and return a formatted output

    Args:
        resources_request: Resource to search, glob-style patterns are supported
        package_paths: Package search path
        resource_type: type of resource to search for. If 'auto', either packages or package families
            are searched, depending on NAME and VERSION
        no_local: Do not look in local paths
        latest: When searching packages, only show the latest version of each package.
        after_time: Only show packages released after the given time. Supported formats are:
            epoch time (eg 1393014494), or relative time (eg -10s, -5m, -0.5h, -10d)
        before_time: Only show packages released before the given time. Supported formats are:
            epoch time (eg 1393014494), or relative time (eg -10s, -5m, -0.5h, -10d)
        validate: Validate each resource that is found
        output_format: Format package output, --format='{qualified_name} | {description}
        sort_results: Print results in sorted order
        search_for_errors: Search for packages containing errors
        suppress_warning: Suppress warning from the output

    return: a tuple (found, search_output)
             found: True if we found information, False otherwise
             search_output: The output of the search
    """

    error_class = None if debug else RezError

    if before_time:
        before_time = get_epoch_time_from_str(before_time)
    if after_time:
        after_time = get_epoch_time_from_str(after_time)

    if package_paths is None:
        pkg_paths = config.nonlocal_packages_path if no_local else None
    else:
        pkg_paths = (package_paths or "").split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    name_pattern = resources_request or '*'
    version_range = None
    if resources_request:
        try:
            req = Requirement(resources_request)
            name_pattern = req.name
            if not req.range.is_any():
                version_range = req.range
        except:
            pass

    type_ = resource_type
    if search_for_errors or (type_ == "auto" and version_range):
        type_ = "package"
        # turn some of the nastier rez-1 warnings into errors
        config.override("error_package_name_mismatch", True)
        config.override("error_version_mismatch", True)
        config.override("error_nonstring_version", True)

    if suppress_warning:
        config.override("warn_none", True)

    # families
    found = False
    family_names = []
    families = iter_package_families(paths=pkg_paths)
    search_output = []
    if sort_results:
        families = sorted(families, key=lambda x: x.name)
    for family in families:
        if family.name not in family_names and \
                fnmatch.fnmatch(family.name, name_pattern):
            family_names.append(family.name)
            if type_ == "auto":
                type_ = "package" if family.name == name_pattern else "family"
            if type_ == "family":
                search_output.append(family.name)
                found = True

    def _handle(e):
        print_error(str(e))

    def _print_resource(r):
        if validate:
            try:
                r.validate_data()
            except error_class as e:
                _handle(e)
                return
        if output_format:
            txt = expand_abbreviations(output_format, fields)
            lines = txt.split("\\n")

            for line in lines:
                try:
                    line_ = r.format(line)
                except error_class as e:
                    _handle(e)
                    break
                if suppress_new_lines:
                    line_ = line_.replace('\n', "\\n")
                search_output.append(line_)
        else:
            search_output.append(r.qualified_name)

    # packages/variants
    if type_ in ("package", "variant"):
        for name in family_names:
            packages = iter_packages(name, version_range, paths=pkg_paths)
            if sort_results or latest:
                packages = sorted(packages, key=lambda x: x.version)
                if latest and packages:
                    packages = [packages[-1]]

            for package in packages:
                if ((before_time or after_time)
                    and package.timestamp
                    and (before_time and package.timestamp >= before_time
                         or after_time and package.timestamp <= after_time)):
                        continue

                if search_for_errors:
                    try:
                        package.validate_data()
                    except error_class as e:
                        _handle(e)
                        found = True
                elif type_ == "package":
                    _print_resource(package)
                    found = True
                elif type_ == "variant":
                    try:
                        package.validate_data()
                    except error_class as e:
                        _handle(e)
                        continue
                    try:
                        for variant in package.iter_variants():
                            _print_resource(variant)
                            found = True
                    except error_class as e:
                        _handle(e)
                        continue
    return found, "\n".join(search_output)

