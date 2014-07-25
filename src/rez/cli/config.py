'''
Print current rez settings.
'''


def setup_parser(parser, completions=False):
    FIELD = parser.add_argument(
        "FIELD", type=str, nargs='?',
        help="print the value of a specific setting")

    if completions:
        from rez.cli._complete_util import ConfigCompleter
        FIELD.completer = ConfigCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.util import pretty_dict

    data = config.data
    if opts.FIELD:
        keys = opts.FIELD.split('.')
        while keys:
            key = keys[0]
            keys = keys[1:]
            try:
                data = data[key]
            except KeyError:
                raise ValueError("no such setting: %r" % opts.FIELD)

    if isinstance(data, (dict, list)):
        print pretty_dict(data)
    else:
        print data
