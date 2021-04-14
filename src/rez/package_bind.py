from __future__ import print_function

from rez.exceptions import RezBindError, _NeverError
from rez import module_root_path
from rez.util import get_close_pkgs
from rez.utils.formatting import columnise
from rez.utils.logging_ import print_error
from rez.config import config
import argparse
import os.path
import os


def get_bind_modules(verbose=False):
    """Get available bind modules.

    Returns:
        dict: Map of (name, filepath) listing all bind modules.
    """
    builtin_path = os.path.join(module_root_path, "bind")
    searchpaths = config.bind_module_path + [builtin_path]
    bindnames = {}

    for path in searchpaths:
        if verbose:
            print("searching %s..." % path)
        if not os.path.isdir(path):
            continue

        for filename in os.listdir(path):
            fpath = os.path.join(path, filename)
            fname, ext = os.path.splitext(filename)
            if os.path.isfile(fpath) and ext == ".py" \
                    and not fname.startswith('_'):
                bindnames[fname] = fpath

    return bindnames


def find_bind_module(name, verbose=False):
    """Find the bind module matching the given name.

    Args:
        name (str): Name of package to find bind module for.
        verbose (bool): If True, print extra output.

    Returns:
        str: Filepath to bind module .py file, or None if not found.
    """
    bindnames = get_bind_modules(verbose=verbose)
    bindfile = bindnames.get(name)

    if bindfile:
        return bindfile

    if not verbose:
        return None

    # suggest close matches
    fuzzy_matches = get_close_pkgs(name, bindnames.keys())

    if fuzzy_matches:
        rows = [(x[0], bindnames[x[0]]) for x in fuzzy_matches]
        print("'%s' not found. Close matches:" % name)
        print('\n'.join(columnise(rows)))
    else:
        print("No matches.")

    return None


def bind_package(name, path=None, version_range=None, no_deps=False,
                 bind_args=None, quiet=False):
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
        no_deps (bool): If True, don't bind dependencies.
        bind_args (list of str): Command line options.
        quiet (bool): If True, suppress superfluous output.

    Returns:
        List of `Variant`: The variant(s) that were installed as a result of
        binding this package.
    """
    pending = set([name])
    installed_variants = []
    installed_package_names = set()

    # bind package and possibly dependencies
    while pending:
        pending_ = pending
        pending = set()
        exc_type = _NeverError

        for name_ in pending_:
            # turn error on binding of dependencies into a warning - we don't
            # want to skip binding some dependencies because others failed
            try:
                variants_ = _bind_package(name_,
                                          path=path,
                                          version_range=version_range,
                                          bind_args=bind_args,
                                          quiet=quiet)
            except exc_type as e:
                print_error("Could not bind '%s': %s: %s"
                            % (name_, e.__class__.__name__, str(e)))
                continue

            installed_variants.extend(variants_)

            for variant in variants_:
                installed_package_names.add(variant.name)

            # add dependencies
            if not no_deps:
                for variant in variants_:
                    for requirement in variant.requires:
                        if not requirement.conflict:
                            pending.add(requirement.name)

            # non-primary packages are treated a little differently
            version_range = None
            bind_args = None
            exc_type = RezBindError

    if installed_variants and not quiet:
        print("The following packages were installed:")
        print()
        _print_package_list(installed_variants)

    return installed_variants


def _bind_package(name, path=None, version_range=None, bind_args=None,
                  quiet=False):
    bindfile = find_bind_module(name, verbose=(not quiet))
    if not bindfile:
        raise RezBindError("Bind module not found for '%s'" % name)

    # load the bind module
    namespace = {}
    with open(bindfile) as stream:
        exec(compile(stream.read(), stream.name, 'exec'), namespace)

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
        print("creating package '%s' in %s..." % (name, install_path))

    bindfunc = namespace.get("bind")
    if not bindfunc:
        raise RezBindError("'bind' function missing in %s" % bindfile)

    variants = bindfunc(path=install_path,
                        version_range=version_range,
                        opts=bind_opts,
                        parser=bind_parser)

    return variants


def _print_package_list(variants):
    packages = set([x.parent for x in variants])
    packages = sorted(packages, key=lambda x: x.name)

    rows = [["PACKAGE", "URI"],
            ["-------", "---"]]
    rows += [(x.name, x.uri) for x in packages]
    print('\n'.join(columnise(rows)))
