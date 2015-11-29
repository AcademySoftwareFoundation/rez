from rez.exceptions import RezBindError
from rez import module_root_path
from rez.util import get_close_pkgs
from rez.utils.formatting import columnise
from rez.vendor.version.requirement import VersionedObject
from rez.config import config
from rez.vendor import argparse
import os.path
import os
import sys


def find_bind_module(name, verbose=False):
    """Find the bind module matching the given name.

    Args:
        name (str): Name of package to find bind module for.
        verbose (bool): If True, print extra output.

    Returns:
        str: Filepath to bind module .py file, or None if not found.
    """
    builtin_path = os.path.join(module_root_path, "bind")
    searchpaths = config.bind_module_path + [builtin_path]
    bindfile = None
    bindnames = {}

    for path in searchpaths:
        if verbose:
            print "searching %s..." % path
        if not os.path.isdir(path):
            continue

        filename = os.path.join(path, name + ".py")
        if os.path.isfile(filename):
            return filename

        for filename in os.listdir(path):
            fpath = os.path.join(path, filename)
            fname, ext = os.path.splitext(filename)
            if os.path.isfile(fpath) and ext == ".py" \
                    and not fname.startswith('_'):
                bindnames[fname] = fpath

    if not verbose:
        return None

    # suggest close matches
    fuzzy_matches = get_close_pkgs(name, bindnames.keys())

    if fuzzy_matches:
        rows = [(x[0], bindnames[x[0]]) for x in fuzzy_matches]
        print "'%s' not found. Close matches:" % name
        print '\n'.join(columnise(rows))
    else:
        print "No matches."

    return None


def bind_package(name, path=None, version_range=None, bind_args=None, quiet=False):
    """Bind software available on the current system, as a rez package.

    Note:
        `bind_args` is provided when software is bound via the 'rez-bind'
        command line tool. Bind modules can define their own command line
        options, and they will be present in `bind_args` if applicable.

    Args:
        name (str): Package name.
        path (str): Package path to install into; local packages path if None.
        version_range (`VersionRange`): If provided, only bind the software if
            it falls within this version range.
        bind_args (list of str): Command line options.
        quiet (bool): If True, suppress superfluous output.
    """
    bindfile = find_bind_module(name, verbose=(not quiet))
    if not bindfile:
        raise RezBindError("Bind module not found for '%s'" % name)

    # load the bind module
    stream = open(bindfile)
    namespace = {}
    exec stream in namespace

    # parse bind module params
    bind_parser = argparse.ArgumentParser(prog="rez bind %s" % name,
                                          description="%s bind module" % name)
    parserfunc = namespace.get("setup_parser")
    if parserfunc:
        parserfunc(bind_parser)
    bind_opts = bind_parser.parse_args(bind_args or [])

    # make the package
    install_path = path or config.local_packages_path

    if not quiet:
        print "creating package '%s' in %s..." % (name, install_path)

    bindfunc = namespace.get("bind")
    if not bindfunc:
        raise RezBindError("'bind' function missing in %s" % bindfile)

    name, version = bindfunc(path=install_path,
                             version_range=version_range,
                             opts=bind_opts,
                             parser=bind_parser)
    if not quiet:
        o = VersionedObject.construct(name, version)
        print "created package '%s' in %s" % (str(o), install_path)
