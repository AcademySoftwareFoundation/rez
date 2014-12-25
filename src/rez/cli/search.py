"""
Search for packages.
"""


def setup_parser(parser, completions=False):
    types_ = ("package", "family", "variant", "auto")
    parser.add_argument("-s", "--sort", action="store_true",
                        help="print results in sorted order")
    parser.add_argument("-t", "--type", default="auto", choices=types_,
                        help="type of resource to search for. If 'auto', "
                        "either packages or package families are searched, "
                        "depending on NAME and VERSION")
    parser.add_argument("--nl", "--no-local", dest="no_local",
                        action="store_true",
                        help="don't search local packages")
    parser.add_argument("--validate", action="store_true",
                        help="validate each resource that is found")
    parser.add_argument("--paths", type=str, default=None,
                        help="set package search path")
    parser.add_argument("-f", "--format", type=str, default=None,
                        help="format package output, eg "
                        "--format='{qualified_name} | {description}'")
    parser.add_argument("-l", "--latest", action="store_true",
                        help="when searching packages, only show the latest "
                        "version of each package")
    parser.add_argument("-e", "--errors", action="store_true",
                        help="search for packages containing errors")
    parser.add_argument("--nw", "--no-warnings", dest="no_warnings",
                        action="store_true",
                        help="suppress warnings")
    parser.add_argument("--before", type=str,
                        help="only show packages released before the given time. "
                        "Supported formats are: epoch time (eg 1393014494), "
                        "or relative time (eg -10s, -5m, -0.5h, -10d)")
    parser.add_argument("--after", type=str,
                        help="only show packages released after the given time. "
                        "Supported formats are: epoch time (eg 1393014494), "
                        "or relative time (eg -10s, -5m, -0.5h, -10d)")
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='?',
        help="packages to search, glob-style patterns are supported")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.exceptions import RezError
    from rez.utils.formatting import get_epoch_time_from_str
    from rez.utils.logging_ import print_error
    from rez.packages_ import iter_package_families, iter_packages
    from rez.vendor.version.requirement import Requirement
    import os.path
    import fnmatch
    import sys

    error_class = None if opts.debug else RezError

    before_time = 0
    after_time = 0
    if opts.before:
        before_time = get_epoch_time_from_str(opts.before)
    if opts.after:
        after_time = get_epoch_time_from_str(opts.after)
    if after_time and before_time and (after_time >= before_time):
        parser.error("non-overlapping --before and --after")

    if opts.paths is None:
        pkg_paths = config.nonlocal_packages_path if opts.no_local else None
    else:
        pkg_paths = (opts.paths or "").split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    name_pattern = opts.PKG or '*'
    version_range = None
    if opts.PKG:
        try:
            req = Requirement(opts.PKG)
            name_pattern = req.name
            if not req.range.is_any():
                version_range = req.range
        except:
            pass

    type_ = opts.type
    if opts.errors or (type_ == "auto" and version_range):
        type_ = "package"
        # turn some of the nastier rez-1 warnings into errors
        config.override("error_package_name_mismatch", True)
        config.override("error_version_mismatch", True)
        config.override("error_nonstring_version", True)

    if opts.no_warnings:
        config.override("warn_none", True)

    # families
    found = False
    family_names = []
    families = iter_package_families(paths=pkg_paths)
    if opts.sort:
        families = sorted(families, key=lambda x: x.name)
    for family in families:
        if family.name not in family_names and \
                fnmatch.fnmatch(family.name, name_pattern):
            family_names.append(family.name)
            if type_ == "auto":
                type_ = "package" if family.name == name_pattern else "family"
            if type_ == "family":
                print family.name
                found = True

    def _handle(e):
        print_error(str(e))

    def _print_resource(r):
        if opts.validate:
            try:
                r.validate_data()
            except error_class as e:
                _handle(e)
                return
        if opts.format:
            try:
                print r.format(opts.format)
            except error_class as e:
                _handle(e)
        else:
            print r.qualified_name

    # packages/variants
    if type_ in ("package", "variant"):
        for name in family_names:
            packages = iter_packages(name, version_range, paths=pkg_paths)
            if opts.sort or opts.latest:
                packages = sorted(packages, key=lambda x: x.version)
                if opts.latest and packages:
                    packages = [packages[-1]]

            for package in packages:
                if ((before_time or after_time)
                    and package.timestamp
                    and (before_time and package.timestamp >= before_time
                         or after_time and package.timestamp <= after_time)):
                    continue

                if opts.errors:
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

    if not found:
        if opts.errors:
            print "no erroneous packages found"
        else:
            print "no matches found"
            sys.exit(1)
