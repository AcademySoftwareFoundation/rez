"""
Command line interface for interacting with different IDEs (Eclipse and 
QtCreator) using Rez.
"""

from rez.cli._main import RezHelpFormatter, SetupRezSubParser
import sys


def setup_parser(parser):

    launcher_subparsers = parser.add_subparsers(dest='ide_subcommand')

    run_parser = launcher_subparsers.add_parser('eclipse', formatter_class=RezHelpFormatter, setup_subparser=SetupRezSubParser("rez.contrib.animallogic.ide.cli.eclipse"))


def get_command_function_from_module(module_name):

    try:
        __import__(module_name, globals(), locals(), [], -1)
    except Exception, e:
        return None

    module = sys.modules[module_name]

    return getattr(module, 'command')


def command(opts, parser):

    module_name = "rez.contrib.animallogic.ide.cli.%s" % opts.ide_subcommand
    func = get_command_function_from_module(module_name)
    func(opts, parser)
