'''
Print current rez settings.
'''

def setup_parser(parser):
    parser.add_argument("-p", "--param", type=str,
                        help="print only the value of a specific parameter")
    parser.add_argument("--pp", "--packages-path", dest="pkgs_path", action="store_true",
                        help="print the effective package search path")

def command(opts, parser):
    from rez.settings import settings
    from rez.vendor import yaml

    def _val(v):
        return ' '.join(str(x) for x in v) if isinstance(v, list) else v

    if opts.pkgs_path:
        paths = settings.get_packages_path()
        print _val(paths)
    elif opts.param:
        value = settings.get(opts.param)
        print _val(value)
    else:
        doc = settings.get_all()
        print yaml.dump(doc, default_flow_style=False)
