from rez.settings import settings
from rez.util import _add_bootstrap_pkg_path
import yaml



def command(opts, parser=None):
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
