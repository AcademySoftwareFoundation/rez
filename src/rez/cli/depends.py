"""
Reverse dependency lookup.
"""


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
    parser.add_argument(
        '--include-all', dest='include_all', action='store_true', default=False,
        help='display all the reverse package dependencies (by default it only displays the anti-packages)'
    )
    parser.add_argument(
        '-f', '--force-update-cache', dest='force_update_cache', action='store_true', default=False,
        help='force-update the cache that stores the reverse package-family dependencies (this cache is automatically '
             'regenerated every 10 minutes by default.'
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="don't print progress bar or depth indicators")

    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package that other packages depend on")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import get_reverse_dependency_tree
    from rez.utils.graph_utils import save_graph, view_graph
    from rez.config import config
    from rez.vendor.pygraph.readwrite.dot import write as write_dot
    from rez import packages
    from rez.vendor.version import version
    import os
    import os.path

    _pr = Printer()

    pkg_name, version_range_str = _extract_package_name_version(opts.PKG)

    config.override("warn_none", True)
    config.override("show_progress", (not opts.quiet))

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list, g, lookup = get_reverse_dependency_tree(
        package_name=pkg_name,
        depth=opts.depth,
        paths=pkg_paths,
        force_update_cache=opts.force_update_cache)

    if len(pkgs_list) <= 2:
        _pr('Can not find any package family depending on %s' % pkg_name)
        return 0

    if version_range_str:
        collector = ReverseVersionDependenciesCollector(pkg_name, version_range_str, pkgs_list[1])
        printer = ReverseVersionDependenciesPrinter(_pr, opts.include_all)
        printer.do_print(collector.iter_dependencies(opts.include_all))

    elif opts.graph or opts.print_graph or opts.write_graph:
        gstr = write_dot(g)
        if opts.print_graph:
            print gstr
        elif opts.write_graph:
            save_graph(gstr, dest_file=opts.write_graph)
        else:
            view_graph(gstr)
        return 0

    for i, pkgs in enumerate(pkgs_list):
        if opts.quiet:
            toks = pkgs
        else:
            toks = ["#%d:" % i] + pkgs
        print ' '.join(toks)

def _extract_package_name_version(input_pkg):

    """Returns the package name and the version range string"""

    name_and_version = input_pkg.split('-')
    if len(name_and_version) != 2:
        return input_pkg, ''
    return name_and_version


class DisplayablePackage(object):

    def __init__(self, name, version, requirement, is_anti_package=False):
        self.name = name
        self.version = version
        self.requirement = requirement
        self.is_anti_package = is_anti_package


class ReverseVersionDependenciesPrinter(object):

    def __init__(self, printer, include_all=True):

        """
        :param printer:
            A rez printer object
        :param include_all:
            tell the printer object whether to display all the packages or only display the anti-packages
        """

        self._printer = printer
        self._include_all = include_all

    def do_print(self, displayable_packages):
        if self._include_all:
            is_anti = None
            for pkg_ in sorted(displayable_packages, key=lambda x: (x.is_anti_package, x.name)):
                if is_anti != pkg_.is_anti_package:
                    self._print_header('%s packages' % ('Incompatible' if pkg_.is_anti_package else 'Compatible'))
                    is_anti = pkg_.is_anti_package
                self._print_package(pkg_)
        else:
            self._print_header('Incompatible Packages')
            for pkg_ in sorted(displayable_packages, key=lambda x: x.name):
                if not pkg_.is_anti_package:
                    continue
                self._print_package(pkg_)

    def _print_header(self, header_msg):
        self._printer('-------------------------\n'
                      '%s\n'
                      '-------------------------' % header_msg)

    def _print_package(self, displayable_package):
        self._printer(
            ('%s-%s' % (displayable_package.name, displayable_package.version)).ljust(60) + displayable_package.requirement
        )


class ReverseVersionDependenciesCollector(object):

    """Collects the reverse version dependencies using the reverse look-up table and the given package name and version
    -range
    """

    def __init__(self, requirement_name, version_range_str, package_families):

        """
        :param requirement_name:
            name of the required package

        :param version_range_str:
            the version range string of the required package

        :param package_families:
            a list of names of the package families that are requiring the given package
        """

        self._requirement_name = requirement_name
        self._requirement_version_range = version.VersionRange(version_range_str)
        self._package_families = package_families

    def iter_dependencies(self, include_all=True):

        """
        include_all:
            Whether to iterate over every packages or only the anti-packages.

        :return:
            An iterator provides one displayable package object at a time.
        """

        for package_family_name in self._package_families:
            displayable_package = self._get_version_dependencies(package_family_name)
            if not displayable_package:
                continue
            if (not include_all) and (not displayable_package.is_anti_package):
                continue
            yield displayable_package

    def _get_version_dependencies(self, package_family_name):

        """A helper function that queries the reverse version dependency.

        :return
            A displayable package object.
        """

        package_obj = sorted(packages.iter_packages(package_family_name), reverse=True, key=lambda x: x.version)[0]
        for requirement in package_obj.requires:
            if requirement.name != self._requirement_name:
                continue
            return DisplayablePackage(
                package_obj.name,
                str(package_obj.version),
                str(requirement),
                not requirement.range.issuperset(self._requirement_version_range)
            )
        return None
