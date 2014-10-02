"""
Reverse dependency lookup.
"""
import os
import os.path

from rez.package_search import get_reverse_dependency_tree
from rez.dot import save_graph, view_graph
from rez.config import config
from rez.colorize import heading, Printer
from rez.vendor.pygraph.readwrite.dot import write as write_dot

from rez import packages
from rez.vendor.version import version


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-d", "--depth", type=int,
        help="dependency tree depth limit")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "-g", "--graph", action="store_true",
        help="display the dependency tree as an image")
    parser.add_argument(
        "--pg", "--print-graph", dest="print_graph", action="store_true",
        help="print the dependency tree as a string")
    parser.add_argument(
        "--wg", "--write-graph", dest="write_graph", type=str, metavar='FILE',
        help="write the dependency tree to FILE")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package that other packages depend on")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):

    _pr = Printer()

    pkg_name, pkg_version_range = _extract_package_name_version(opts.PKG)
    version_range = version.VersionRange(pkg_version_range)

    # try to get the latest package
    try:
        pkg_obj = max(packages.iter_packages(pkg_name, version_range), key=lambda x: x.version)
    except (StopIteration, ValueError), e:
        _pr('Invalid rez package: %s' % opts.PKG)
        return 1

    config.override("warn_none", True)

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list, g = get_reverse_dependency_tree(
        package_name=pkg_name,
        depth=opts.depth,
        paths=pkg_paths)

    if len(pkgs_list) <= 2:
        _pr('Can not find any package family depending on %s' % opts.PKG)
        return 0

    if pkg_version_range:
        _present_version_dependencies(pkg_obj, pkgs_list[1])

    elif opts.graph or opts.print_graph or opts.write_graph:
        gstr = write_dot(g)
        if opts.print_graph:
            print gstr
        elif opts.write_graph:
            save_graph(gstr, dest_file=opts.write_graph)
        else:
            view_graph(gstr)
    else:
        _pr()
        for i, pkgs in enumerate(pkgs_list):
            _pr("depth %d:" % i, heading)
            _pr(" ".join(pkgs))

    return 0

def _extract_package_name_version(input_pkg):

    """Returns the package name and the version range string"""

    name_and_version = input_pkg.split('-')
    if len(name_and_version) != 2:
        return input_pkg, ''
    return name_and_version

def _present_version_dependencies(package, package_families):

    """Displays the package version reverse dependencies"""

    printer = Printer()
    printer('Getting version dependencies...... (family count: %s - the larger this value the longer it might take)' % len(package_families))
    version_dependencies = []
    for package_family_name in package_families:
        req_and_pkg_and_latest = _get_version_dependencies(package, package_family_name)
        if req_and_pkg_and_latest:
            version_dependencies.append(req_and_pkg_and_latest)
    if not version_dependencies:
        printer('Can not find any package depending on %s-%s' % (package.name, package.version))
    else:
        printer('List of upstream packages:')
        printer('\n'.join([_format_info(req, pkg, latest) for req, pkg, latest in version_dependencies]))

def _format_info(requirement, pkg_obj, latest_version):
    if pkg_obj.version == latest_version:
        return ('%s-%s' % (pkg_obj.name, pkg_obj.version)).ljust(60) + str(requirement)
    return ('%s-%s(%s)' % (pkg_obj.name, pkg_obj.version, latest_version)).ljust(60) + str(requirement)

def _get_version_dependencies(required_package, package_family_name):

    """A helper function that checks the reverse dependency on the version-level.

    It iterates the package-version objects of the given package family from the latest to the oldest, returning the
     first object whose requirements contain the given required package object.
    """

    index = 0
    latest_version = None
    for pkg_obj in sorted(packages.iter_packages(package_family_name), reverse=True, key=lambda x: x.version):
        if index == 0:
            latest_version = pkg_obj.version
        for requirement in pkg_obj.requires:
            if requirement.name != required_package.name:
                continue
            if requirement.range.issuperset(version.VersionRange(str(required_package.version))):
                return requirement, pkg_obj, latest_version
        index += 1
    return None