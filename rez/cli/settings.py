from rez.settings import settings
import yaml



def command(opts, parser=None):
    if opts.param:
        value = settings.get(opts.param)
        if isinstance(value, list):
            print ' '.join(str(x) for x in value)
        else:
            print value
    else:
        doc = settings.get_all()
        print yaml.dump(doc, default_flow_style=False)
