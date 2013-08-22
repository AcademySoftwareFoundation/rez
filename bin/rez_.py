#!!REZ_PYTHON_BINARY!

import os
import sys
import inspect
import argparse
import pkgutil

def get_parser_defaults(parser):
    return dict((act.dest, act.default) for act in parser._actions)

def subpackages(packagemod):
    """
    Given a module object, returns an iterator which yields a tuple (modulename, moduleobject, ispkg)
    for the given module and all it's submodules/subpackages.
    """
    modpkgs = []
    modpkgs_names = set()
    if hasattr(packagemod, '__path__'):
        yield packagemod.__name__, packagemod, True
        for importer, modname, ispkg in pkgutil.walk_packages(packagemod.__path__,
                                                              packagemod.__name__+'.'):
            if modname not in sys.modules:
                try:
                    #mod = importer.find_module(modname).load_module(modname)
                    __import__(modname, globals(), locals(), [], -1)
                    mod = sys.modules[modname]
                except Exception, e:
                    print>>sys.stderr, "rez: error importing %s: %s" %  ( modname, e)
            else:
                mod = sys.modules[modname]
            yield modname, mod, ispkg
    else:
        yield packagemod.__name__, packagemod, False

def main():
    import rez.cli
    parser = argparse.ArgumentParser("rez")
    subparsers = []
    parents = []
    for name, mod, ispkg in subpackages(rez.cli):
        cmdname = name.split('.')[-1].replace('_', '-')
        if ispkg:
            if cmdname == 'cli':
                title = 'commands'
            else:
                title = (cmdname + ' subcommands')
            subparsers.append(parser.add_subparsers(title=title))
            parents.append(name)
            continue
        elif not name.startswith(parents[-1]):
            parents.pop()
            subparsers.pop()
        assert mod.__doc__, "command module %s must have a module-level docstring (used as the command help)" % name
        assert hasattr(mod, 'command'), "command module %s must provide a command() function" % name
        assert hasattr(mod, 'setup_parser'), "command module %s  must provide a setup_parser() function" % name

        brief = mod.__doc__.strip('\n').split('\n')[0]
        subparser = subparsers[-1].add_parser(cmdname,
                                              description=mod.__doc__,
                                              help=brief)
        mod.setup_parser(subparser)
        subparser.set_defaults(func=mod.command)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()