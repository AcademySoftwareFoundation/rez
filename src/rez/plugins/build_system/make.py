from rez.build_system import BuildSystem
from rez.exceptions import BuildSystemError
from rez import plugin_factory
import os.path



class MakeBuildSystem(BuildSystem):
    executable = BuildSystem.find_executable("make")

    @classmethod
    def name(cls):
        return "make"

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isfile(os.path.join(path, "Makefile"))

    def __init__(self, working_dir):
        super(MakeBuildSystem, self).__init__(working_dir)
        raise NotImplementedError


class MakeBuildSystemFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return MakeBuildSystem
