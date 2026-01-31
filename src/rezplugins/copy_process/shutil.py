# Copyright Contributors to the Rez Project


"""
Copies files using Python's shutil module.
"""

import os

from rez.utils.copy_process import CopyProcess
from rez.utils.filesystem import replacing_copy


class ShutilCopyProcess(CopyProcess):
    """The default copy process.

    This process copies files using rez's wrappers of shutil.
    """

    @classmethod
    def name(cls):
        return "shutil"

    def execute(self, src_dir, dest_dir, names=None, follow_symlinks=False,
                verbose=False):
        if names is not None:
            # Copy filtered names.
            for name in names:
                src = os.path.join(src_dir, name)
                dest = os.path.join(dest_dir, name)
                replacing_copy(src, dest, follow_symlinks=follow_symlinks)
        else:
            # Copy full names.
            replacing_copy(src_dir, dest_dir, follow_symlinks=follow_symlinks)


def register_plugin():
    return ShutilCopyProcess
