"""
The main command-line entry point.
"""
import os
import sys
import pkgutil
import textwrap
import argparse
from rez.cli._util import error
from rez import __version__
import rez.sigint


class RezHelpFormatter(argparse.HelpFormatter):
    remainder_descs = {
        "BUILD_ARG": "[-- ARG [ARG ...] [-- ARG [ARG ...]]]"
    }

    def _fill_text(self, text, width, indent):
        #text = self._whitespace_matcher.sub(' ', text).strip()
        text = text.strip()
        return '\n\n'.join([textwrap.fill(x, width,
                                          initial_indent=indent,
                                          subsequent_indent=indent) for x in text.split('\n\n')])

    # allow for more meaningful remainder desc than '...'
    def _format_args(self, action, default_metavar):
        if action.nargs == argparse.REMAINDER:
            desc = self.remainder_descs.get(default_metavar)
            return desc or "..."
        else:
            return super(RezHelpFormatter, self)._format_args(action, default_metavar)

    # show default value for options with choices
    def _get_help_string(self, action):
        help_ = action.help
        if action.choices and ('%(default)' not in action.help) \
            and (action.default is not None) and \
                (action.default is not argparse.SUPPRESS):
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help_ += ' (default: %(default)s)'
        return help_

def subpackages(packagemod):
    """
    Given a module object, returns an iterator which yields a tuple (modulename, ispkg)
    for the given module and all it's submodules/subpackages.
    """
    if hasattr(packagemod, '__path__'):
        yield packagemod.__name__, True
        for _, modname, ispkg in pkgutil.walk_packages(packagemod.__path__,
                                                       packagemod.__name__ + '.'):
            yield modname, ispkg
    else:
        yield packagemod.__name__, False

class LazySubParsersAction(argparse._SubParsersAction):
    """
    argparse Action which calls the `setup_subparser` function provided to
    `LazyArgumentParser`.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        parser_name = values[0]

        # this bit is taken directly from argparse:
        try:
            parser = self._name_parser_map[parser_name]
        except KeyError:
            tup = parser_name, ', '.join(self._name_parser_map)
            msg = _('unknown parser %r (choices: %s)' % tup)
            raise argparse.ArgumentError(self, msg)

        self._setup_subparser(parser_name, parser)

        caller = super(LazySubParsersAction, self).__call__
        return caller(parser, namespace, values, option_string)

    def _setup_subparser(self, parser_name, parser):
        if hasattr(parser, 'setup_subparser'):
            help_ = parser.setup_subparser(parser_name, parser)
            if help_ is not None:
                if help_ == argparse.SUPPRESS:
                    self._choices_actions = [act for act in self._choices_actions \
                                             if act.dest != parser_name]
                else:
                    help_action = self._find_choice_action(parser_name)
                    if help_action is not None:
                        help_action.help = help_

    def _find_choice_action(self, parser_name):
        for help_action in self._choices_actions:
            if help_action.dest == parser_name:
                return help_action

class LazyArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser sub-class which accepts an additional `setup_subparser`
    argument for lazy setup of sub-parsers.

    `setup_subparser` is passed 'parser_name', 'parser', and can return a help
    string.
    """
    def __init__(self, *args, **kwargs):
        self.setup_subparser = kwargs.pop('setup_subparser', None)
        super(LazyArgumentParser, self).__init__(*args, **kwargs)
        self.register('action', 'parsers', LazySubParsersAction)

    def format_help(self):
        """
        sets up all sub-parsers when help is requested
        """
        if self._subparsers:
            for action in self._subparsers._actions:
                if isinstance(action, LazySubParsersAction):
                    for parser_name, parser in action._name_parser_map.iteritems():
                        action._setup_subparser(parser_name, parser)
        return super(LazyArgumentParser, self).format_help()

class SetupRezSubParser(object):
    """
    callback class for lazily setting up rez sub-parsers
    """
    def __init__(self, module_name):
        self.module_name = module_name

    def __call__(self, parser_name, parser):
        mod = self.get_module()

        if not mod.__doc__:
            error("command module %s must have a module-level "
                  "docstring (used as the command help)" % self.module_name)
            return argparse.SUPPRESS
        if not hasattr(mod, 'command'):
            error("command module %s must provide a command() "
                  "function" % self.module_name)
            return argparse.SUPPRESS
        if not hasattr(mod, 'setup_parser'):
            error("command module %s  must provide a setup_parser() "
                  "function" % self.module_name)
            return argparse.SUPPRESS

        mod.setup_parser(parser)
        parser.description = mod.__doc__
        parser.set_defaults(func=mod.command)
        # add the common args to the subparser
        _add_common_args(parser)

        # optionally, return the brief help line for this sub-parser
        brief = mod.__doc__.strip('\n').split('\n')[0]
        return brief

    def get_module(self):
        if self.module_name not in sys.modules:
            try:
                #mod = importer.find_module(modname).load_module(modname)
                __import__(self.module_name, globals(), locals(), [], -1)
            except Exception, e:
                error("importing %s: %s" % (self.module_name, e))
                return None
        return sys.modules[self.module_name]

def module_to_command_name(module_name):
    return module_name.split('.')[-1].rstrip('_').replace('_', '-')

def _add_common_args(parser):
    parser.add_argument("--debug", dest="debug", action="store_true",
                        help=argparse.SUPPRESS)

def run():
    import rez.cli
    parser = LazyArgumentParser("rez")

    parser.add_argument("-V", "--version", action="version",
                        version="Rez %s" % __version__)

    # add args common to all subcommands... we add them both to the top parser,
    # AND to the subparsers, for two reasons:
    #  1) this allows us to do EITHER "rez --debug build" OR
    #     "rez build --debug"
    #  2) this allows the flags to be used when using either "rez" or
    #     "rez-build" - ie, this will work: "rez-build --debug"

    _add_common_args(parser)

    subparsers = []
    parents = []
    for module_name, ispkg in subpackages(rez.cli):
        short_name = module_name.split('.')[-1]
        if short_name.startswith('_'):
            continue
        cmdname = module_to_command_name(module_name)
        if ispkg:
            # a package with sub-modules
            subparser = parser.add_subparsers(dest='cmd',
                                              metavar='COMMAND')
            # recurse down a level
            subparsers.append(subparser)
            parents.append(module_name)
        else:
            # a module
            if not module_name.startswith(parents[-1]):
                # go up a level
                parents.pop()
                subparsers.pop()

            subparsers[-1].add_parser(cmdname,
                                      help='',  # required so that it can be setup later
                                      formatter_class=RezHelpFormatter,
                                      setup_subparser=SetupRezSubParser(module_name))

    opts = parser.parse_args()

    if opts.debug:
        from rez.util import set_rm_tmpdirs
        exc_type = None
        set_rm_tmpdirs(False)
    else:
        exc_type = Exception

    try:
        returncode = opts.func(opts)
    except NotImplementedError as e:
        import traceback
        raise Exception(traceback.format_exc())
    except exc_type as e:
        print >> sys.stderr, "rez: %s: %s" \
                             % (e.__class__.__name__, str(e))
        sys.exit(1)

    sys.exit(returncode or 0)

if __name__ == '__main__':
    run()
