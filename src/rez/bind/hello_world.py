"""
Creates the 'hello_world' testing package.

Note: Even though this is a python-based package, it does not list python as a
requirement. This is not typical! This package is intended as a very simple test
case, and for that reason we do not want any dependencies.
"""
from __future__ import absolute_import
from rez.package_maker_ import make_py_package, root, code_provider
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version


@code_provider
def commands():
    env.PATH.append('{this.root}/bin')


@code_provider
def hello_world_tool():
    import sys
    from optparse import OptionParser

    p = OptionParser()
    p.add_option("-q", dest="quiet", action="store_true",
        help="quiet mode")
    p.add_option("-r", dest="retcode", type="int", default=0,
        help="exit with a non-zero return code")
    opts,args = p.parse_args()

    if not opts.quiet:
        print "Hello Rez World!"
    sys.exit(opts.retcode)


def bind(path, version_range=None, opts=None, parser=None):
    version = Version("1.0")
    if version_range and version not in version_range:
        raise RezBindError("hello_world is a test package that can only "
                           "be bound as version 1.0")

    with make_py_package("hello_world", version, path) as pkg:
        pkg.set_tools("hello_world")
        pkg.set_commands(commands)

        pkg.add_python_tool(name="hello_world",
                            body=hello_world_tool,
                            relpath=root("bin"))

    return ("hello_world", version)
