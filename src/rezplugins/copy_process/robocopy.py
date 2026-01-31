# Copyright Contributors to the Rez Project


"""
Copies files using Robust File Copy for Windows.
"""

import os
import subprocess

from rez.config import config
from rez.utils.copy_process import CopyProcess
from rez.utils.logging_ import print_warning


class RobocopyCopyProcess(CopyProcess):
    """This process copies files using robocopy.exe.
    """

    schema_dict = {
        "multithreading": bool,
    }

    @classmethod
    def name(cls):
        return "robocopy"

    def execute(self, src_dir, dest_dir, names=None, follow_symlinks=False,
                verbose=False):
        args = ["robocopy", src_dir, dest_dir, "/MIR", "/NFL", "/NDL"]
        if names:
            all_excludes = [os.path.join(src_dir, item)
                            for item in os.listdir(src_dir)
                            if item not in names]
            exclude_files = list(filter(os.path.isfile, all_excludes))
            exclude_dirs = list(filter(os.path.isdir, all_excludes))
            if exclude_files:
                args.extend(["/XF"] + exclude_files)
            if exclude_dirs:
                args.extend(["/XD"] + exclude_dirs)
        if not follow_symlinks:
            args.extend(["/SL", "/SJ"])
        settings = config.plugins.copy_process.robocopy
        if settings.multithreading:
            args.append("/MT")

        exit_code = subprocess.call(
            args,
            stdout=subprocess.DEVNULL if not verbose else None
        )

        if exit_code == 0:
            print_warning("No files were copied using robocopy")
            return

        # Lower exit codes are just warnings.
        # https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy#exit-return-codes
        if exit_code >= 8:
            raise RuntimeError("Unable to copy files using robocopy")


def register_plugin():
    return RobocopyCopyProcess
