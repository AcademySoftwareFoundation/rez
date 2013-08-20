#!!REZ_PYTHON_BINARY!

import os
import sys
import inspect
import argparse
import pkgutil
import rez.commands

def subpackages(packagemod):
    """
    Given a module object, returns an iterator which yields a tuple (modulename, moduleobject, ispkg)
    for the given module and all it's submodules/subpackages.
    """
    modpkgs = []
    modpkgs_names = set()
    if hasattr(packagemod, '__path__'):
        for importer, modname, ispkg in pkgutil.walk_packages(packagemod.__path__,
                                                              packagemod.__name__+'.'):
            if modname not in sys.modules:
                try:
                    mod = importer.find_module(modname).load_module(modname)
                except Exception, e:
                    print "error importing %s: %s" %  ( modname, e)
            else:
                mod = sys.modules[modname]
            yield modname, mod, ispkg
    else:
        yield packagemod.__name__, packagemod, False

def main():
    parser = argparse.ArgumentParser("rez")
    subparsers = parser.add_subparsers(title='subcommands')
    for name, mod, ispkg in subpackages(rez.commands):
        assert mod.__doc__, "command module %s must have a module-level docstring (used as the command help)" % name
        assert hasattr(mod, 'command'), "command module %s must provide a command() function" % name
        assert hasattr(mod, 'setup_parser'), "command module %s  must provide a setup_parser() function" % name

        brief = mod.__doc__.strip('\n').split('\n')[0]

        subparser = subparsers.add_parser(name.split('.')[-1],
                                          description=mod.__doc__,
                                          help=brief)
        mod.setup_parser(subparser)
        subparser.set_defaults(func=mod.command)

    parser.parse_args()

if __name__ == '__main__':
    main()