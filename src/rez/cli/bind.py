'''
Create a Rez package for existing software.
'''
from rez.vendor import argparse


def setup_parser(parser, completions=False):
    parser.add_argument("-i", "--install-path", dest="install_path", type=str,
                        default=None, metavar="PATH",
                        help="install path, defaults to local package path")
    parser.add_argument("-s", "--search", action="store_true",
                        help="search for the binding but do not do the bind")
    parser.add_argument("PKG", type=str,
                        help='package to bind')
    parser.add_argument("BIND_ARG", metavar="ARG", nargs=argparse.REMAINDER,
                        help="extra arguments to the target bind module. "
                        "Use '-h' to show help for the module")


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.exceptions import RezBindError
    from rez import module_root_path
    from rez.util import get_close_pkgs
    from rez.utils.formatting import columnise, PackageRequest
    from rez.vendor.version.requirement import VersionedObject
    import os.path
    import os
    import sys

    # gather the params
    install_path = (config.local_packages_path if opts.install_path is None
                    else opts.install_path)
    req = PackageRequest(opts.PKG)
    name = req.name
    version_range = None if req.range.is_any() else req.range
    if req.conflict:
        parser.error("PKG cannot be a conflict requirement")

    # find the bind module
    builtin_path = os.path.join(module_root_path, "bind")
    searchpaths = config.bind_module_path + [builtin_path]
    bindfile = None
    bindnames = {}

    for path in searchpaths:
        if opts.verbose:
            print "searching %s..." % path
        if not os.path.isdir(path):
            continue

        filename = os.path.join(path, name + ".py")
        if os.path.isfile(filename):
            if opts.search:
                print filename
                sys.exit(0)
            else:
                bindfile = filename
                break
        else:
            for filename in os.listdir(path):
                fpath = os.path.join(path, filename)
                fname, ext = os.path.splitext(filename)
                if os.path.isfile(fpath) and ext == ".py" \
                        and not fname.startswith('_'):
                    bindnames[fname] = fpath

    if not bindfile:
        fuzzy_matches = get_close_pkgs(name, bindnames.keys())

        if opts.search:
            if fuzzy_matches:
                rows = [(x[0], bindnames[x[0]]) for x in fuzzy_matches]
                print "'%s' not found. Close matches:" % name
                print '\n'.join(columnise(rows))
            else:
                print "No matches."
            sys.exit(0)
        else:
            msg = "bind module not found for '%s'" % name
            if fuzzy_matches:
                matches_s = ', '.join(x[0] for x in fuzzy_matches)
                msg += "\ndid you mean one of: %s" % matches_s

            raise RezBindError(msg)

    # load the bind module
    stream = open(bindfile)
    namespace = {}
    exec stream in namespace

    # parse bind module params
    bind_parser = argparse.ArgumentParser(prog = "rez bind %s" % name,
                                          description="%s bind module" % name)
    parserfunc = namespace.get("setup_parser")
    if parserfunc:
        parserfunc(bind_parser)
    bind_opts = bind_parser.parse_args(opts.BIND_ARG)

    # make the package
    if opts.verbose:
        print "creating package '%s' in %s..." % (name, install_path)

    bindfunc = namespace.get("bind")
    if not bindfunc:
        raise RezBindError("'bind' function missing in %s" % bindfile)

    name, version = bindfunc(path=install_path,
                             version_range=version_range,
                             opts=bind_opts,
                             parser=bind_parser)

    o = VersionedObject.construct(name, version)
    print "created package '%s' in %s" % (str(o), install_path)
