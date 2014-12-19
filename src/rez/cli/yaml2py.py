"""
Convert a package.yaml file to a package.py file.
"""


def setup_parser(parser, completions=False):
    pass


def command(opts, parser, extra_arg_groups=None):
    from rez.packages_ import get_developer_package
    from rez.serialise import FileFormat
    from StringIO import StringIO
    import os.path
    import os
    import sys

    cwd = os.getcwd()
    filepath_py = os.path.join(cwd, "package.py")
    if os.path.exists(filepath_py):
        print >> sys.stderr, "%r already exists." % filepath_py
        sys.exit(1)

    filepath_yaml = os.path.join(cwd, "package.yaml")
    if not os.path.isfile(filepath_yaml):
        print >> sys.stderr, "Expected file 'package.yaml' in the current directory"
        sys.exit(1)

    package = get_developer_package(cwd)
    if package is None:
        print >> sys.stderr, "Couldn't load the package at %r" % cwd
        sys.exit(1)

    buf = StringIO()
    package.print_info(buf=buf, format_=FileFormat.py)
    contents = buf.getvalue()
    buf.close()

    with open(filepath_py, 'w') as f:
        f.write(contents)

    print
    print "SUCCESS!"
    print "The new 'package.py' will be used in preference to the 'package.yaml'."
    print "You should delete the 'package.yaml' once it is no longer needed."
