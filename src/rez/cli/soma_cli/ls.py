"""
List hierarchy nodes (shows, shots etc) under a given directory.
"""


def setup_parser(parser, completions=False):
    PATH_action = parser.add_argument(
        "PATH", type=str, nargs='?',
        help="path to search for hierarchy nodes under, defaults to cwd.")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        PATH_action.completer = FilesCompleter(dirs=True, files=False)


def command(opts, parser, extra_arg_groups=None):
    print "hello from soma ls"
