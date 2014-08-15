from rezgui import organisation_name, application_name
from rezgui.objects.Config import Config
from rez.vendor import yaml
import os.path


filepath = os.path.dirname(__file__)
filepath = os.path.join(filepath, "rezguiconfig")
with open(filepath) as f:
    settings = yaml.load(f.read())

config = Config(settings,
                organization=organisation_name,
                application=application_name)
