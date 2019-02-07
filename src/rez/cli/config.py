'''
Print current rez settings.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--search-list", dest="search_list", action="store_true",
        help="list the config files searched")
    parser.add_argument(
        "--source-list", dest="source_list", action="store_true",
        help="list the config files sourced")
    FIELD_action = parser.add_argument(
        "FIELD", type=str, nargs='?',
        help="print the value of a specific setting")

    if completions:
        from rez.cli._complete_util import ConfigCompleter
        FIELD_action.completer = ConfigCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.utils.yaml import dump_yaml

    if opts.search_list:
        for filepath in config.filepaths:
            print filepath
        return

    if opts.source_list:
        for filepath in config.sourced_filepaths:
            print filepath
        return

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
        txt = dump_yaml(data).strip()
        print txt
    else:
        print data


