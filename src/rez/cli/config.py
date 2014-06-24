'''
Print current rez settings.
'''
import sys


def setup_parser(parser):
    parser.add_argument("FIELD", type=str, nargs='?',
                        help="print the value of a specific setting")


def command(opts, parser):
    from rez.config import config
    if opts.FIELD:
        from rez.util import ObjectStringFormatter
        formatter = ObjectStringFormatter(config, expand=None)
        try:
            print formatter.format("{%s}" % opts.FIELD)
        except AttributeError:
            print >> sys.stderr, "no such setting: %r" % opts.FIELD
            sys.exit(1)
    else:
        from rez.vendor import yaml
        print yaml.dump(config.data, default_flow_style=False)
