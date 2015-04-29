"""
Print a package.yaml file in package.py format.
"""


def setup_parser(parser, completions=False):
    PKG_action = parser.add_argument(
        "PATH", type=str, nargs='?',
        help="path to search for package.yaml, cwd if not provided")


def command(opts, parser, extra_arg_groups=None):
    from rez.packages_ import get_developer_package
    from rez.serialise import FileFormat
    import os.path
    import os
    import sys

    if opts.PATH:
        path = os.path.expanduser(opts.PATH)
    else:
        path = os.getcwd()
    if os.path.basename(path) == "package.yaml":
        path = os.path.dirname(path)

    filepath_yaml = os.path.join(path, "package.yaml")
    if not os.path.isfile(filepath_yaml):
        print >> sys.stderr, "Expected file '%s'" % filepath_yaml
        sys.exit(1)

    package = get_developer_package(path)
    if package is None:
        print >> sys.stderr, "Couldn't load the package at %r" % cwd
        sys.exit(1)

    package.print_info(format_=FileFormat.py)
