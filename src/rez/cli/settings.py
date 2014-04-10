'''
Print current rez settings.
'''

def setup_parser(parser):
    parser.add_argument("-p", "--param", type=str,
                        help="print only the value of a specific parameter")
    parser.add_argument("--pp", "--packages-path", dest="pkgs_path", action="store_true",
                        help="print the package search path, including any "
                        "system paths")

def command(opts, parser=None):
    from rez.settings import settings
    from rez.util import _add_bootstrap_pkg_path
    import yaml

    def _val(v):
        return ' '.join(str(x) for x in v) if isinstance(v, list) else v

    if opts.pkgs_path:
        paths = _add_bootstrap_pkg_path(settings.packages_path)
        print _val(paths)
    elif opts.param:
        value = settings.get(opts.param)
        print _val(value)
    else:
        doc = settings.get_all()
        print yaml.dump(doc, default_flow_style=False)
