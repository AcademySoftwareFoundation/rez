"""
Builds packages on remote hosts
"""
from rez.build_process_ import BuildProcessHelper
from rez.exceptions import BuildError


class RemoteBuildProcess(BuildProcessHelper):
    """The default build process.

    This process builds a package's variants sequentially, on remote hosts.
    """
    @classmethod
    def name(cls):
        return "remote"

    def build(self, install_path=None, clean=False, install=False, variants=None):
        raise NotImplementedError("coming soon...")

    def release(self, release_message=None, variants=None):
        raise NotImplementedError("coming soon...")


def register_plugin():
    return RemoteBuildProcess
