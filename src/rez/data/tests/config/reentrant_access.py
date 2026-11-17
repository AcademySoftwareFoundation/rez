# Reads a setting during its own evaluation. Before the re-entrancy guard
# this recursed; with it, the nested read is served shipped defaults and the
# load completes - this file's own values then apply as normal.
from rez.config import config as _cfg

optionvars = {"warn_all_seen_during_eval": _cfg.warn_all}
warn_all = True
