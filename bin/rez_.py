#!!REZ_PYTHON_BINARY!

import os
import sys
import inspect
import argparse
import pkgutil
import rez.cli
import textwrap

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
                    rez.cli.error("importing %s: %s" %  ( modname, e))
            else:
                mod = sys.modules[modname]
            yield modname, mod, ispkg
    else:
        yield packagemod.__name__, packagemod, False

class DescriptionHelpFormatter(argparse.HelpFormatter):
    """Help message formatter which retains double-newlines in descriptions
    and adds default values
    """

    def _fill_text(self, text, width, indent):
        #text = self._whitespace_matcher.sub(' ', text).strip()
        text = text.strip()
        return '\n\n'.join([textwrap.fill(x, width,
                                          initial_indent=indent,
                                          subsequent_indent=indent) for x in text.split('\n\n')])

    def _get_help_string(self, action):
        help = action.help
        if '%(default)' not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help += ' (default: %(default)s)'
        return help


@rez.cli.redirect_to_stderr
def main():
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
        if not mod.__doc__:
            rez.cli.error("command module %s must have a module-level docstring (used as the command help)" % name)
        if not hasattr(mod, 'command'):
            rez.cli.error("command module %s must provide a command() function" % name)
        if not hasattr(mod, 'setup_parser'):
            rez.cli.error("command module %s  must provide a setup_parser() function" % name)

        brief = mod.__doc__.strip('\n').split('\n')[0]
        subparser = subparsers[-1].add_parser(cmdname,
                                              description=mod.__doc__,
                                              formatter_class=DescriptionHelpFormatter,
                                              help=brief)
        mod.setup_parser(subparser)
        subparser.set_defaults(func=mod.command)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()