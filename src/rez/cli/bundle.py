"""
Bundle a package and all of it's dependencies into a single directory.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't load local packages")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "--exclude", type=str, nargs='+', metavar="RULE",
        help="add package exclusion filters, eg '*.beta'. Note that these are "
             "added to the globally configured exclusions")
    parser.add_argument(
        "--include", type=str, nargs='+', metavar="RULE",
        help="add package inclusion filters, eg 'mypkg', 'boost-*'. Note that "
             "these are added to the globally configured inclusions")
    parser.add_argument(
        "--max-fails", type=int, default=-1, dest="max_fails",
        metavar='N',
        help="abort if the number of failed configuration attempts exceeds N")
    parser.add_argument(
        "--ni", "--no-implicit", dest="no_implicit",
        action="store_true",
        help="don't add implicit packages to the request")
    parser.add_argument(
        "--time-limit", type=int, default=-1,
        dest="time_limit", metavar='SECS',
        help="abort if the resolve time exceeds SECS")
    parser.add_argument(
        "--no-cache", dest="no_cache", action="store_true",
        help="do not fetch cached resolves")
    parser.add_argument(
        "--no-passive", action="store_true",
        help="only print actions that affect the solve (has an effect only "
             "when verbosity is enabled)")
    parser.add_argument(
        "--no-filters", dest="no_filters", action="store_true",
        help="turn off package filters. Note that any filters specified with "
             "--exclude/--include are still applied")
    parser.add_argument(
        "--stats", action="store_true",
        help="print advanced solver stats")
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='*',
        help='packages to bundle')

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.resolved_context import ResolvedContext
    from rez.resolver import ResolverStatus
    from rez.package_filter import PackageFilterList, Rule
    from rez.config import config
    import os
    import sys
    import os.path

    context = None
    request = opts.PKG

    if opts.paths is None:
        pkg_paths = (config.nonlocal_packages_path
                     if opts.no_local else None)
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    if context is None:
        # create package filters
        if opts.no_filters:
            package_filter = PackageFilterList()
        else:
            package_filter = PackageFilterList.singleton.copy()

        for rule_str in (opts.exclude or []):
            rule = Rule.parse_rule(rule_str)
            package_filter.add_exclusion(rule)

        for rule_str in (opts.include or []):
            rule = Rule.parse_rule(rule_str)
            package_filter.add_inclusion(rule)

        # perform the resolve
        context = ResolvedContext(package_requests=request,
                                  timestamp=None,
                                  package_paths=pkg_paths,
                                  building=False,
                                  package_filter=package_filter,
                                  add_implicit_packages=(not opts.no_implicit),
                                  verbosity=opts.verbose,
                                  max_fails=opts.max_fails,
                                  time_limit=opts.time_limit,
                                  caching=(not opts.no_cache),
                                  suppress_passive=opts.no_passive,
                                  print_stats=opts.stats)

    success = (context.status == ResolverStatus.solved)
    if not success:
        context.print_info(buf=sys.stderr)
        sys.exit(1)

    context = context.to_dict()
    resolved_packages = context['resolved_packages']
    requested_package_names = {package: {"name": package, "version": None} for package in context['package_requests']}
    packages = []

    for package in resolved_packages:
        v = package['variables']
        file_path = "{}/{}/{}".format(v['location'], v['name'], v['version'])
        packages.append({"path": file_path, "name": v['name'], "version": v['version']})
        if v['name'] in requested_package_names:
            requested_package_names[v['name']]['version'] = v['version']
    try:
        dir_name = create_resolve_dir(requested_package_names)
        copy_all_packages_to_bundle(packages, dir_name)
        print "Done! Bundle at {}/{}".format(os.getcwd(), dir_name)
        print "Run: export REZ_PACKAGES_PATH=$REZ_PACKAGES_PATH:{}/{}".format(os.getcwd(), dir_name)
    except Exception as e:
        print e



def create_resolve_dir(requested_packages):
    import os
    import errno

    dir_name = get_resolve_dir_name(requested_packages)
    try:
        os.makedirs(dir_name)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e
    return dir_name


def copy_all_packages_to_bundle(resolved_packages, dir_name):
    from multiprocessing import Pool
    pool = Pool(processes=8)
    # add dir_name to each
    resolved_packages = [(package, dir_name) for package in resolved_packages]
    pool.map(copy_dir, resolved_packages)
    pool.close()


def get_resolve_dir_name(requested_packages):
    dir_name = ''
    for package in requested_packages.values():
        dir_name += "{}-{}+".format(package['name'], package['version'])
    dir_name = dir_name[0:-1]  # strip the last +
    return dir_name


def copy_dir(args):
    import shutil
    package, dir_name = args
    print "Copying {} to bundle.".format(package['path'])
    try:
        shutil.copytree(package['path'], "{}/{}/{}".format(dir_name, package['name'], package['version']))
    except:
        pass  # can fail with dead symlinks
    return package['name']
