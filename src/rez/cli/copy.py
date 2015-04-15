"""
Get a list of a package's plugins.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "-va", "--variant", default=None,  nargs='+', type=int, metavar="INDEX",
        help="select the (zero-indexed) variant to be installed.")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package to be copied.")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):

    from rez.config import config
    from rez.packages_ import iter_packages
    import os

    config.override("warn_none", True)

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    mongo_location_t = "mongo:host=%s,port=%i,namespace=%s"
    mongo_location_d = mongo_location_t % ('localhost', 27017, '%s')
    for package in iter_packages(opts.PKG, paths=pkg_paths):
        destination_location = mongo_location_d % package.wrapped.location
        print destination_location
        for variant in package.iter_variants():
            if opts.variant is not None:
                if variant.index != variant:
                    continue
            variant.install(destination_location)
