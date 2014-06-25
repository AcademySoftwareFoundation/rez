'''
Print current rez settings.
'''


def setup_parser(parser):
    parser.add_argument("FIELD", type=str, nargs='?',
                        help="print the value of a specific setting")


def command(opts, parser):
    from rez.config import config
    from rez.util import AttrDictWrapper
    from rez.config import _PluginConfigs
    from rez.vendor import yaml

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
        print yaml.dump(data, default_flow_style=False)
    else:
        print data
