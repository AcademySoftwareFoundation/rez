# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Make-based build system
"""
from rez.build_system import BuildSystem
import os.path


class MakeBuildSystem(BuildSystem):
    @classmethod
    def name(cls) -> str:
        return "make"

    @classmethod
    def is_valid_root(cls, path, package=None):
        return os.path.isfile(os.path.join(path, "Makefile"))

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts: bool = False,
                 verbose: bool = False, build_args=[], child_build_args=[]) -> None:
        super(MakeBuildSystem, self).__init__(working_dir)
        raise NotImplementedError


def register_plugin():
    return MakeBuildSystem
