import os

from rez.vendor.whichcraft import whichcraft


def which(cmd, mode=os.F_OK | os.X_OK, path=None, env=None):
    return whichcraft.which(cmd, mode, path, env)
