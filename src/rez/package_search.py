"""
Default algorithms for searching for packages based on some criteria. Package
repository plugins may implement these algorithms instead, because they may be
able to search packages much faster - for example, in a database-based package
repository. The algorithms here serve as backup for those package repositories
that do not provide an implementation.
"""

import fnmatch
from collections import defaultdict
import sys

from rez.packages import iter_package_families, iter_packages, get_latest_package
from rez.exceptions import PackageFamilyNotFoundError, ResourceContentError
from rez.util import ProgressBar
from rez.utils.colorize import critical, info, error, Printer
from rez.vendor.pygraph.classes.digraph import digraph
from rez.utils.formatting import expand_abbreviations

from rez.config import config

from rez.vendor.version.requirement import Requirement


def get_reverse_dependency_tree(package_name, depth=None, paths=None,
                                build_requires=False,
                                private_build_requires=False):
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
        build_requires (bool): If True, includes packages' build_requires.
        private_build_requires (bool): If True, include `package_name`'s
            private_build_requires.

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
        it = iter_packages(name=package_name_, paths=paths)
        packages = list(it)
        if not packages:
            continue

        pkg = max(packages, key=lambda x: x.version)
        requires = []

        for variant in pkg.iter_variants():
            pbr = (private_build_requires and pkg.name == package_name)

            requires += variant.get_requires(
                build_requires=build_requires,
                private_build_requires=pbr
            )

        for req in requires:
            if not req.conflict:
                lookup[req.name].add(package_name_)

        bar.next()

    bar.finish()

    # perform traversal
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
    """Items from a search.

    Will contain either a package, variant, or name of a package family (str).
    """
    def __init__(self, resource, resource_type, validation_error=None):
        self.resource = resource
        self.resource_type = resource_type
        self.validation_error = validation_error


class ResourceSearcher(object):
    """Search for resources (packages, variants or package families).
    """
    def __init__(self, package_paths=None, resource_type=None, no_local=False,
                 latest=False, after_time=None, before_time=None, validate=False):
        """Create resource search.

        Args:
            package_paths (list of str): Package search path
            resource_type (str): type of resource to search for. One of "family",
                "package" or "variant". If None, is determined based on format of
                `resources_request`.
            no_local (bool): Do not look in local paths
            latest (bool): Only return latest version if resource type is
                package or variant
            after_time (int): Only show packages released after the given
                epoch time
            before_time (int): Only show packages released before the given
                epoch time
            validate (bool): Validate each resource that is found. If False,
                results are not validated (ie, `validation_error` is None).

        Returns:
            List of `ResourceSearchResult` objects
        """
        self.resource_type = resource_type
        self.no_local = no_local
        self.latest = latest
        self.after_time = after_time
        self.before_time = before_time
        self.validate = validate

        if package_paths:
            self.package_paths = package_paths
        elif no_local:
            self.package_paths = config.nonlocal_packages_path
        else:
            self.package_paths = None

    def iter_resources(self, resources_request=None):
        """Iterate over matching resources.

        Args:
            resources_request (str): Resource to search, glob-style patterns
                are supported. If None, returns all matching resource types.

        Returns:
            2-tuple:
            - str: resource type (family, package, variant);
            - Iterator of `ResourceSearchResult`: Matching resources. Will be
              in alphabetical order if families, and version ascending for
              packages or variants.
        """

    def search(self, resources_request=None):
        """Search for resources.

        Args:
            resources_request (str): Resource to search, glob-style patterns
                are supported. If None, returns all matching resource types.

        Returns:
            2-tuple:
            - str: resource type (family, package, variant);
            - List of `ResourceSearchResult`: Matching resources. Will be in
              alphabetical order if families, and version ascending for
              packages or variants.
        """

        # Find matching package families
        name_pattern, version_range = self._parse_request(resources_request)

        family_names = set(
            x.name for x in iter_package_families(paths=self.package_paths)
            if fnmatch.fnmatch(x.name, name_pattern)
        )

        family_names = sorted(family_names)

        # determine what type of resource we're searching for
        if self.resource_type:
            resource_type = self.resource_type
        elif version_range or len(family_names) == 1:
            resource_type = "package"
        else:
            resource_type = "family"

        if not family_names:
            return resource_type, []

        # return list of family names (validation is n/a in this case)
        if resource_type == "family":
            results = [ResourceSearchResult(x, "family") for x in family_names]
            return "family", results

        results = []

        # iterate over packages/variants
        for name in family_names:
            it = iter_packages(name, version_range, paths=self.package_paths)
            packages = sorted(it, key=lambda x: x.version)

            if self.latest and packages:
                packages = [packages[-1]]

            for package in packages:
                # validate and check time (accessing timestamp may cause
                # validation fail)
                try:
                    if package.timestamp:
                        if self.after_time and package.timestamp < self.after_time:
                            continue
                        if self.before_time and package.timestamp >= self.before_time:
                            continue

                    if self.validate:
                        package.validate_data()

                except ResourceContentError as e:
                    if resource_type == "package":
                        result = ResourceSearchResult(package, "package", str(e))
                        results.append(result)

                    continue

                if resource_type == "package":
                    result = ResourceSearchResult(package, "package")
                    results.append(result)
                    continue

                # iterate variants
                try:
                    for variant in package.iter_variants():
                        if self.validate:
                            try:
                                variant.validate_data()
                            except ResourceContentError as e:
                                result = ResourceSearchResult(
                                    variant, "variant", str(e))
                                results.append(result)
                                continue

                        result = ResourceSearchResult(variant, "variant")
                        results.append(result)

                except ResourceContentError:
                    # this may happen if 'variants' in package is malformed
                    continue

        return resource_type, results

    @classmethod
    def _parse_request(cls, resources_request):
        name_pattern = resources_request or '*'
        version_range = None

        try:
            req = Requirement(name_pattern)
            name_pattern = req.name
            if not req.range.is_any():
                version_range = req.range
        except:
            pass

        return name_pattern, version_range


class ResourceSearchResultFormatter(object):
    """Formats search results.
    """
    fields = (
        'pre_commands', 'tools', 'uuid', 'build_requires', 'version', 'timestamp',
        'release_message', 'private_build_requires', 'revision', 'description',
        'base', 'authors', 'variants', 'commands', 'name', 'changelog',
        'post_commands', 'requires', 'root', 'index', 'uri', 'num_variants',
        'qualified_name'
    )

    def __init__(self, output_format=None, suppress_newlines=False):
        """
        Args:
            output_format (str): String that can contain keywords such as
                "{base}". These (or their appreviations) will be expanded into
                the matching resource attribute, or left unexpanded if the
                attribute does not exist. The '\\n' literal will be converted
                into newlines. Defaults to qualified name.
            suppress_newlines (bool): If True, replace newlines with '\\n'.
        """
        self.output_format = output_format
        self.suppress_newlines = suppress_newlines

    def print_search_results(self, search_results, buf=sys.stdout):
        """Print formatted search results.

        Args:
            search_results (list of `ResourceSearchResult`): Search to format.
        """
        formatted_lines = self.format_search_results(search_results)
        pr = Printer(buf)

        for txt, style in formatted_lines:
            pr(txt, style)

    def format_search_results(self, search_results):
        """Format search results.

        Args:
            search_results (list of `ResourceSearchResult`): Search to format.

        Returns:
            List of 2-tuple: Text and color to print in.
        """
        formatted_lines = []

        for search_result in search_results:
            lines = self._format_search_result(search_result)
            formatted_lines.extend(lines)

        return formatted_lines

    def _format_search_result(self, resource_search_result):
        formatted_lines = []

        # just ignore formatting if family
        if resource_search_result.resource_type == "family":
            family_name = resource_search_result.resource
            return [(family_name, info)]

        if resource_search_result.validation_error:
            line1 = (resource_search_result.resource.qualified_name, error)
            line2 = (resource_search_result.validation_error, critical)
            formatted_lines.extend([line1, line2])

        elif self.output_format:
            txt = expand_abbreviations(self.output_format, self.fields)
            lines = txt.split("\\n")

            for line in lines:
                try:
                    line_ = resource_search_result.resource.format(line)
                except ResourceContentError as e:
                    # formatting may read attrib that causes validation fail
                    line1 = (resource_search_result.resource.qualified_name, error)
                    line2 = (str(e), critical)
                    formatted_lines.extend([line1, line2])
                    break

                if self.suppress_newlines:
                    line_ = line_.replace('\n', "\\n")

                formatted_lines.append((line_, info))

        else:
            line = (resource_search_result.resource.qualified_name, info)
            formatted_lines.append(line)

        return formatted_lines


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
