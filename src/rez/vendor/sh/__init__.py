# putting rez-specific code here, because this file wouldn't exist in a
# "normal" distribution of sh

from rez.config import config
from . import sh
sh.ErrorReturnCode.truncate_cap = config.shell_error_truncate_cap