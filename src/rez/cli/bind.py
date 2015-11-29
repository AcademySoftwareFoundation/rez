'''
Create a Rez package for existing software.
'''
from rez.vendor import argparse


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--quickstart", action="store_true",
        help="bind a set of standard packages to get started")
    parser.add_argument(
        "-r", "--release", action="store_true",
        help="install to release path; overrides -i")
    parser.add_argument(
        "-i", "--install-path", dest="install_path", type=str,
        default=None, metavar="PATH",
        help="install path, defaults to local package path")
    parser.add_argument(
        "-s", "--search", action="store_true",
        help="search for the bind module but do not perform the bind")
    parser.add_argument(
        "PKG", type=str, nargs='?',
        help='package to bind')
    parser.add_argument(
        "BIND_ARGS", metavar="ARG", nargs=argparse.REMAINDER,
        help="extra arguments to the target bind module. Use '-h' to show help "
        "for the module")


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.package_bind import bind_package, find_bind_module
    from rez.utils.formatting import PackageRequest

    if opts.release:
        install_path = config.release_packages_path
    elif opts.install_path:
        install_path = opts.install_path
    else:
        install_path = config.local_packages_path

    if opts.quickstart:
        # note: in dependency order, do not change
        for name in ["platform",
                     "arch",
                     "os",
                     "python",
                     "rez",
                     "rezgui",
                     "setuptools",
                     "pip"]:

            bind_package(name, path=install_path)
        return

    if not opts.PKG:
        parser.error("PKG required.")

    req = PackageRequest(opts.PKG)
    name = req.name
    version_range = None if req.range.is_any() else req.range

    if opts.search:
        find_bind_module(name, verbose=True)
    else:
        bind_package(name,
                     path=install_path,
                     version_range=version_range,
                     bind_args=opts.BIND_ARGS)
