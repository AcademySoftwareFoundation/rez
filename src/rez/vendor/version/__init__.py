# putting rez-specific code here, because this file wouldn't exist in a
# "normal" distribution of sh

from . import version

try:
    from rez.config import config
except ImportError:
    # if there's an ImportError, we're in the middle of importing config - if
    # this is the case, we have code at the end of config to set this...
    pass
else:
    version.default_make_token = getattr(version, config.version_token)