"""
Show current Rez settings
"""

def setup_parser(parser):
    pass


def command(opts, parser=None):
    from rez.settings import settings
    import yaml

    doc = settings.get_all()
    print yaml.dump(doc, default_flow_style=False)
