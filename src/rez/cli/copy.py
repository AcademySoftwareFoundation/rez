"""
Get a list of a package's plugins.
"""


def setup_parser(parser, completions=False):
    types_ = ("package", "family", "variant", "auto")
    parser.add_argument(
        "-va", "--variant", default=None,  nargs='+', type=int, metavar="INDEX",
        help="select the (zero-indexed) variant to be installed.")
    parser.add_argument(
        "-t", "--type", default="auto", choices=types_,
        help="type of resource to search for. If 'auto', either packages or "
        "package families are searched, depending on the value of PKG")
    parser.add_argument(
        "--np", "--no-prompt", dest="no_prompt", action="store_true",
        help="install without prompting first")
    parser.add_argument(
        "-l", "--latest", action="store_true",
        help="when searching packages, only show the latest version of each "
        "package")
    parser.add_argument(
        "--nw", "--no-warnings", dest="no_warnings", action="store_true",
        help="suppress warnings")
    parser.add_argument(
        "-q", "--quiet", dest="quiet", action="store_true",
        help="silence")
    parser.add_argument(
        "--all", "--all", dest="all", action="store_true",
        help="suppress warnings")
    parser.add_argument(
        "-z", "--dry-run", dest="dry_run", action="store_true",
        help="dry run")
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='?',
        help="packages to search, glob-style patterns are supported")
    parser.add_argument(
        "SRC_REPOSITORY", type=str,
        help="source repository location")
    parser.add_argument(
        "DEST_REPOSITORY", type=str,
        help="destination repository location")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.exceptions import PackageMetadataError
    from rez.packages_ import iter_package_families, iter_packages, get_latest_package
    from rez.vendor.version.requirement import Requirement
    from rez.util import ProgressBar
    import sys
    import os.path
    import fnmatch
    import traceback

    type_ = opts.type
    version_range = None

    src_paths = []
    if not opts.PKG or opts.all:
        name_pattern = '*'
        type_ = 'all'
        _repo_type = opts.SRC_REPOSITORY.split('@')[0]
        for path in config.packages_path:
            # normalise
            parts = path.split('@', 1)
            if len(parts) == 1:
                parts = ("filesystem", parts[0])

            repo_type, location = parts
            if _repo_type != repo_type:
                continue
            if repo_type == "filesystem":
                location = os.path.realpath(location)

            normalised_path = "%s@%s" % (repo_type, location)
            src_paths.append(normalised_path)
    else:
        req = Requirement(opts.PKG)
        name_pattern = req.name
        if not req.range.is_any():
            version_range = req.range

    if type_ == "auto" and version_range:
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
    families = iter_package_families(paths=src_paths)

    for family in families:
        if family.name not in family_names and \
                fnmatch.fnmatch(family.name, name_pattern):
            family_names.append(family.name)
            if type_ == "auto":
                type_ = "package" if family.name == name_pattern else "family"
            if type_ == "family":
                found = True

    # packages/variants
    install = {}
    found_packages_count = found_variant_count = 0

    bar = ProgressBar("Searching", len(family_names))

    for name in family_names:
        bar.next()
        try:
            if opts.latest:
                packages = [get_latest_package(name, version_range, paths=src_paths, error=True)]
            else:
                packages = iter_packages(name, version_range, paths=src_paths)

            for package in packages:
                for variant in package.iter_variants():
                    if opts.variant is not None:
                        if variant.index not in opts.variant:
                            continue
                    repo_destination = _initialize_destination(opts.DEST_REPOSITORY, variant)
                    family_lut = install.get(repo_destination, [])
                    family_lut.append(variant)
                    install.update({repo_destination: family_lut})
                    found_variant_count += 1
                found_packages_count += 1
        except PackageMetadataError:
            pass
    bar.finish()

    destination_count = len(install)
    if destination_count == 0 or (type_ == 'family' and not found):
        print "no matches found. nothing to install."
        sys.exit(1)

    if not opts.no_prompt:
        txt = 'Found %i variant/s in %i package/s.\n' % (found_variant_count, found_packages_count)
        txt += 'Do you want to continue? (y)es or (n)o or (d)etails:'
        y_n = ''
        while len(y_n) == 0:
            y_n = raw_input(txt).lower()
            if y_n in ['n', 'no', 'q', '0']:
                sys.exit(1)
            elif y_n in ['d', 'details']:
                from pprint import pprint as pp
                pp(install)
                y_n = ''
            elif y_n in ['y', 'yes', 'si', 'oui', '1']:
                break
            y_n = ''

    failed = {}
    installed_variants_count = 0
    bar = ProgressBar("Copying", found_variant_count)
    for destination, variants in install.iteritems():
        for variant in variants:
            try:
                variant.install(destination, dry_run=opts.dry_run)
                installed_variants_count += 1
            except:
                qn = variant.qualified_name
                failed_lut = failed.get(qn, '')
                failed_lut += ''.join(traceback.format_exc())
                failed.update({qn: failed_lut})
            finally:
                bar.next()
    bar.finish()
    not_installed = found_variant_count - installed_variants_count
    if not_installed:
        print 'Failed installing %i variants.\nDetails:' % not_installed
        if not opts.quiet:
                for f, e in failed.iteritems():
                    print f
                    print e

    print 'Finished installing %i variant/s found in %i package/s into %i destination/s. ' % (installed_variants_count, found_packages_count, destination_count)


def _initialize_destination(dest_path, variant):
    # need to specialize this.
    #
    from rez.config import config
    parts = dest_path.split('@', 1)
    if len(parts) == 1:
        raise RuntimeError

    repo_type, location = parts

    settings = config.plugins.package_repository.mongo
    parts = location.split(',', 3)

    host, port, ns = [settings.host, settings.port, None]
    for part in parts:
        args = part.split('=', 2)
        if len(args) != 2:
            continue
        k, v = args[0], args[1]
        if k.startswith('host'):
            host = str(v)
        elif k.startswith('port'):
            port = int(v)
        elif k.startswith('namespace'):
            ns = str(v)
    if not ns:
        if location and len(parts) == 1:
            ns = location
        else:
            ns = variant.wrapped.location

    dest_location_t = "mongo@host=%s,port=%i,namespace=%s"
    dest_location_d = dest_location_t % (host, port, '%s')
    return dest_location_d % ns
    #resource.wrapped.location
