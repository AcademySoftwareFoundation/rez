"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""

import os
import fnmatch
import sys

from rez.packages_ import iter_package_families, iter_packages, get_latest_package
from rez.exceptions import PackageFamilyNotFoundError
from rez.util import ProgressBar
from rez.utils.colorize import critical, info, Printer
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
        packages = list(iter_packages(name=package_name_, paths=paths))
        if not packages:
            continue
        pkg = max(packages, key=lambda x: x.version)

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

class ResourceSearchResult(object):
    """
    Data container to store the result of a rez search
    """
    def __init__(self, resource, resource_type, validation_error=None):
        self.resource = resource
        self.resource_type = resource_type
        self.validation_error = validation_error

    def has_validation_error(self):
        return bool(self.validation_error)

class ResourceSearchResultFormatter(object):
    """
    Formats the output of a search based on some options.
    """

    def __init__(self, output_format, suppress_new_lines=False, debug=False):
        """
        output_format: Format package output, --format='{qualified_name} | {description}
        sort_results: Print results in sorted order
        """

        self.output_format = output_format
        self.suppress_new_lines = suppress_new_lines
        self.debug = debug

    def format_search_result(self, resource_search_result):
        """
        resource_search_result: a ResourceSearchResult
        """
        error_class = None if self.debug else RezError

        formatted_search_results = []
        if resource_search_result.has_validation_error():
            formatted_search_results.append((resource_search_result.resource.qualified_name, info))
            formatted_search_results.append((resource_search_result.validation_error, critical))

        elif self.output_format:
            txt = expand_abbreviations(self.output_format, fields)
            lines = txt.split("\\n")

            for line in lines:
                try:
                    line_ = resource_search_result.resource.format(line)
                except error_class as e:
                    formatted_search_results.append((str(e), critical))
                    break
                if self.suppress_new_lines:
                    line_ = line_.replace('\n', "\\n")
                formatted_search_results.append((line_, info))
        else:
            formatted_search_results.append((resource_search_result.resource.qualified_name, info))

        return formatted_search_results

class ResourceSearchResultPrinter(object):

    def __init__(self, buf=sys.stdout):
        """
        Args:
            buf (file-like object): Where to print this info to.
        """
        self.pr = Printer(buf)

    def print_search_result(self, message, style):
        self.pr(message, style)

class ResourceSearch(object):
    """
    Search resource information
    """
    def __init__(self, resources_request, package_paths=None, resource_type="auto", no_local=False,
                 latest=False, after_time=0, before_time=0, validate=False, sort_results=False,
                 search_for_errors=False, debug=False):
        """
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
            search_for_errors: Search for packages containing errors

        return: search_result, a list of ResourceSearchResult objects

        """
        self.resources_request = resources_request
        self.package_paths = package_paths
        self.resource_type = resource_type
        self.no_local = no_local
        self.latest = latest
        self.after_time = after_time
        self.before_time = before_time
        self.validate = validate
        self.sort_results = sort_results
        self.search_for_errors = search_for_errors
        self.debug = debug

    def search(self):

        before_time = get_epoch_time_from_str(self.before_time)
        after_time = get_epoch_time_from_str(self.after_time)

        search_result = []

        self._configure_package_paths()

        name_pattern, version_range = self._get_name_pattern_and_version_range()

        family_names = self._get_families_matching_pattern(name_pattern)

        if self.sort_results:
            family_names = sorted(family_names)

        if self.resource_type == "auto":
            self.resource_type = self._work_out_resource_type(family_names, name_pattern, version_range)

        if self.resource_type == "family":
            for family in family_names:
                search_result.append(ResourceSearchResult(family, self.resource_type))

        elif self.resource_type in ("package", "variant"):

            self._modify_output_configs()

            for name in family_names:

                packages = iter_packages(name, version_range, paths=self.package_paths)
                packages = sorted(packages, key=lambda x: x.version) if self.sort_results else packages

                packages = self.filter_packages_by_time(packages, before_time, after_time)

                search_result.extend(self._validate_resources(packages))

        return search_result


    def _configure_package_paths(self,):

        if self.package_paths is None:
            self.package_paths = config.nonlocal_packages_path if self.no_local else None
        else:
            self.package_paths = (self.package_paths or "").split(os.pathsep)
            self.package_paths = [os.path.expanduser(x) for x in self.package_paths if x]

    def _check_for_resource_error(self,resource):

        error_class = None if self.debug else RezError

        try:
            resource.validate_data()
            return None
        except error_class as e:
            return str(e)

    def _validate_resources(self, packages):

        search_result = []
        for package in packages:

            if self.search_for_errors:
                error = self._check_for_resource_error(package)
                if error:
                    search_result.append(ResourceSearchResult(package, self.resource_type, validation_error=error))
            elif self.resource_type == "package":
                error = self._check_for_resource_error(package)
                search_result.append(ResourceSearchResult(package, self.resource_type, validation_error=error))
                if self.validate and error:
                    break

            elif self.resource_type == "variant":
                error = self._check_for_resource_error(package)
                if error:
                    search_result.append(ResourceSearchResult(package, "package", validation_error=error))
                    continue

                for variant in package.iter_variants():
                    error = self._check_for_resource_error(package)
                    search_result.append(ResourceSearchResult(variant, self.resource_type, validation_error=error))
                    if self.validate and error:
                        break
                    else:
                        continue

        return search_result

    def filter_packages_by_time(self, packages, before_time, after_time):
        """
        Filter out packages that were released with a timestamp that is after_time > timestamp > before_time

        Args:
             packages: A list of packages
             before_time: timestamp, packages released before the given timestamp will be filtered out
             after_time: timestamp, packages released after the given timestamp will be filtered out

        return: A list with the filtered packages
        """
        filtered_packages = []

        if self.latest and packages:
            packages = sorted(packages, key=lambda x: x.version)
            packages = [packages[-1]]

        for package in packages:
            if ((before_time or after_time) and package.timestamp
                and (before_time and package.timestamp >= before_time or after_time and package.timestamp <= after_time)):
                continue
            filtered_packages.append(package)

        return filtered_packages

    def _modify_output_configs(self):

        if self.search_for_errors or self.resource_type == "package":
            # turn some of the nastier rez-1 warnings into errors
            config.override("error_package_name_mismatch", True)
            config.override("error_version_mismatch", True)
            config.override("error_nonstring_version", True)

    def _work_out_resource_type(self, family_names, name_pattern, version_range):
        """
        Find out what type of resource it is based on the pattern of the request

        Args:
            family_names: A list with family names
            name_pattern: the name part of a package or family
            version_range: Version range

        return: the resource_type, whether it is package or family
        """
        resource_type = 'auto'
        if version_range:
            return "package"

        for family in family_names:
            resource_type = "package" if family == name_pattern else "family"
        return resource_type

    def _get_name_pattern_and_version_range(self):
        """
        Works out the patten to search based on tht resource request.

        return: a pattern with the name and a version range (if it is a package)
        """

        name_pattern = self.resources_request or '*'
        version_range = None
        if self.resources_request:
            try:
                req = Requirement(self.resources_request)
                name_pattern = req.name
                if not req.range.is_any():
                    version_range = req.range
            except:
                pass
        return name_pattern, version_range

    def _get_families_matching_pattern(self, name_pattern):
        """
        Get the families matching the given patten

        Args:
            name_pattern: the name part of a package or family

        return: a list with the matching families
        """

        family_names = []
        families = iter_package_families(paths=self.package_paths)

        for family in families:
            if family.name not in family_names and fnmatch.fnmatch(family.name, name_pattern):
                family_names.append(family.name)

        return family_names

