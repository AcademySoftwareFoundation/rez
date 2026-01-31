# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from rez.plugin_managers import plugin_manager
from rez.config import config


class CopyProcess(object):
    """A CopyProcess copies files.
    """
    @classmethod
    def name(cls):
        raise NotImplementedError

    def execute(self, src_dir, dest_dir, names=None, follow_symlinks=False,
                verbose=False):
        """Copy a list of files.
        Args:
            src_dir (str): Directory to copy from
            dest_dir (str): Directory to copy to
            names (list of str, optional): Files and subdirectories that
                should be copied, relative to `src_dir`. If `None`, all
                items should be copied. Subdirectories should be copied
                recursively.
            follow_symlinks (bool) Whether to follow symlinks and copy
                their targets instead of copying the symlinks themselves
            verbose (bool): Verbose mode.
        """
        raise NotImplementedError


def get_copy_plugin(name=None):
    """
    Returns:
        CopyProcess: plugin instance
    """
    name = name or config.default_copy_process
    cls_ = plugin_manager.get_plugin_class("copy_process", name)
    return cls_()
