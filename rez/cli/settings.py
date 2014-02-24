"""
Show current Rez settings
"""

def setup_parser(parser):
    parser.add_argument("-p", "--param", type=str,
                        help="print only the value of a specific parameter")


def command(opts, parser=None):
    from rez.settings import settings
    import yaml

    if opts.param:
        value = settings.get(opts.param)
        if isinstance(value, list):
            print ' '.join(str(x) for x in value)
        else:
            print value
    else:
        doc = settings.get_all()
        print yaml.dump(doc, default_flow_style=False)
