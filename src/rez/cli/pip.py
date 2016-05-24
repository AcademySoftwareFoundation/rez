"""
Install a pip-compatible python package, and its dependencies, as rez packages.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--pip-version", dest="pip_ver", metavar="VERSION",
        help="pip version (rez package) to use, default is latest")
    parser.add_argument(
        "--python-version", dest="py_ver", metavar="VERSION",
        help="python version (rez package) to use, default is latest. Note "
        "that the pip package(s) will be installed with a dependency on "
        "python-MAJOR.MINOR. You can also provide a comma-separated list to "
        "install for multiple pythons at once, eg '2.6,2.7'")
    parser.add_argument(
        "PACKAGE",
        help="package to install or archive/url to install from")


def command(opts, parser, extra_arg_groups=None):
    from rez.pip import pip_install_package

    if opts.py_ver:
        py_vers = opts.py_ver.strip(',').split(',')
    else:
        py_vers = None

    pip_install_package(opts.PACKAGE,
                        pip_version=opts.pip_ver,
                        python_versions=py_vers)
