#!!REZ_PYTHON_BINARY!
from __future__ import with_statement
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


def spawn_logged_subprocess(logfile, overwrite, args):
    import subprocess
    import datetime
    
    # remove the '--logfile' arg from the given args
    new_args = list(args)
    try:
        logfile_arg_start = new_args.index('--logfile')
    except ValueError:
        # if using "--logfile=myfile.txt" syntax, find the arg, and strip
        # out only that one
        for i, arg in enumerate(new_args):
            if arg.startswith('--logfile='):
                logfile_arg_start = i
                logfile_arg_end = i + 1
                break
        else:
            raise RuntimeError("logfile arg was given, but could not find in %r"
                               % new_args)
    else:
        # if using "--logfile myfile.txt" syntax, strip out two args
        logfile_arg_end = logfile_arg_start + 2
    del new_args[logfile_arg_start:logfile_arg_end]

    # set up the logdir    
    logdir = os.path.dirname(logfile)
    if logdir and not os.path.isdir(logdir):
        try:
            os.mkdir(logdir)
        except Exception:
            print "error creating logdir"

    tee_args = ['tee']
    if overwrite:
        file_mode = 'w'
    else:
        file_mode = 'a'
        tee_args.append('-a')
        
    # write a small header, with timestamp, to the logfile -- helps separate
    # different runs if appending
    with open(logfile, file_mode) as file_handle:
        file_handle.write('='* 80 + '\n')
        file_handle.write('%s - CWD: %s\n' % (datetime.datetime.now(),
                                              os.getcwd()))
        file_handle.write('%s\n' % ' '.join(args))

    # spawn a new subprocess, without the --logfile arg, and pipe the output
    # from it through tee...
    new_environ = dict(os.environ)
    current_logs = new_environ.get('REZ_ACTIVE_LOGS', '').split(':')
    current_logs.append(logfile)
    new_environ['REZ_ACTIVE_LOGS'] = ':'.join(current_logs)
    
    rez_proc = subprocess.Popen(new_args, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=new_environ)
        
    tee = subprocess.Popen(tee_args + [logfile], stdin=rez_proc.stdout)
    tee.communicate()


@rez.cli.redirect_to_stderr
def main():
    parser = argparse.ArgumentParser("rez")
    
    # add args common to all subcommands... we add them both to the top parser,
    # AND to the subparsers, for two reasons:
    #  1) this allows us to do EITHER "rez --logfile=foo build" OR
    #     "rez build --logfile=foo"
    #  2) this allows the flags to be used when using either "rez" or
    #     "rez-build" - ie, this will work: "rez-build --logfile=foo"
    
    common_args = [
        ('--logfile',
            {'help': 'log all stdout/stderr output to the given file, in'
             ' addition to printing to the screen'}),
        ('--logfile-overwrite',
            {'action': 'store_true', 'help':'log all stdout/stderr output to'
             ' the given file, in addition to printing to the screen'}),
    ]
    for arg, arg_settings in common_args:
        parser.add_argument(arg, **arg_settings)

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
        
        # add the common args to the subparser
        for arg, arg_settings in common_args:
            subparser.add_argument(arg, **arg_settings)

    args = parser.parse_args()
    
    if args.logfile:
        # check to see if we're in a subprocess, and a parent process is already
        # logging to the given logfile...
        current_logs = os.environ.get('REZ_ACTIVE_LOGS', '').split(':')
        # standardize the logfile, so we can compare it...
        logfile = os.path.normcase(os.path.normpath(os.path.realpath(os.path.abspath(args.logfile))))
        if logfile not in current_logs:
            spawn_logged_subprocess(logfile, args.logfile_overwrite, sys.argv)
            return
     
    args.func(args)

if __name__ == '__main__':
    main()
