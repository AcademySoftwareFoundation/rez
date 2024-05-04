# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import sys
import shutil
import struct
import typing
import pathlib
import tempfile
import subprocess

import distlib.util
import packaging.tags

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# carefully import some sourcefiles that are standalone
source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.cli._entry_points import get_specifications


SCRIPT_TEMPLATE = """#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import re
import sys
import platform
# If -E is not passed, then inject it and re-execute outself.
# Note that this is not done on Windows because the Windows launcher
# already does this.
if not sys.flags.ignore_environment and platform.system() != 'Windows':
    args = [sys.executable, '-E'] + sys.argv
    if os.getenv('REZ_LAUNCHER_DEBUG'):
        print('Launching:', ' '.join(args))
    os.execvp(sys.executable, args)
from rez.cli._entry_points import {0}
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
    sys.exit({0}())
"""


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.__tmp_dir: pathlib.Path | None = None

    def initialize(self, version: str, build_data: typing.Dict[str, typing.Any]) -> None:
        self.__tmp_dir = pathlib.Path(tempfile.mkdtemp()).resolve()
        try:
            self._initialize(build_data=build_data)
        except Exception:
            self._cleanup()
            raise

    def _initialize(self, *, build_data: typing.Dict[str, typing.Any]) -> None:
        """
        This occurs immediately before each build.

        Any modifications to the build data will be seen by the build target.
        """
        self.__tmp_dir = pathlib.Path(tempfile.mkdtemp()).resolve()

        if sys.platform == "win32":
            bits = '64' if struct.calcsize("P") == 8 else '32'
            platform_suffix = '-arm' if distlib.util.get_platform() == 'win-arm64' else ''

            cli_launcher_path = self.__tmp_dir / f"t{bits}{platform_suffix}"
            gui_launcher_path = self.__tmp_dir / f"w{bits}{platform_suffix}"

            mapping = {"win-amd64": "x86_64", "win-arm64": "aarch64"}
            zig_args = [
                sys.executable,
                "-m",
                "ziglang",
                "cc",
                os.path.join("launcher", "launcher.c"),
                "-std=c99",
                # Optimize for size.
                "-Os",
                # Prevent undefined behavior from becoming illegal instructions.
                "-fno-sanitize=undefined",
                "-target",
                "{0}-windows".format(mapping[distlib.util.get_platform()]),
                "-DWIN32",
                "-DNDEBUG",
            ]

            args = zig_args + ["-D_CONSOLE", "-o", os.fspath(cli_launcher_path)]
            self.app.display_waiting(f"Compiling CLI launcher using: {' '.join(args)!r}")
            # We compile the console (CLI) launcher.
            subprocess.check_call(args)

            args = zig_args + ["-D_WINDOWS", "-o", os.fspath(gui_launcher_path)]
            self.app.display_waiting(f"Compiling GUI launcher using: {' '.join(args)!r}")
            # We compile the windows (GUI) launcher.
            subprocess.check_call(args)

        scripts = {}
        for command, spec in get_specifications().items():
            filename = command
            if sys.platform == "win32":
                filename = f"{filename}-script.py"

            path = self.__tmp_dir / filename
            with open(path, "w") as fd:
                fd.write(SCRIPT_TEMPLATE.format(spec.func))

            if sys.platform == "win32":
                launcher_path = cli_launcher_path
                if spec.type == "window":
                    launcher_path = gui_launcher_path

                exe_path = self.__tmp_dir / f"{command}.exe"
                shutil.copy(launcher_path, exe_path)

                scripts[exe_path] = os.path.join("rez", exe_path.name)

            scripts[path] = os.path.join("rez", filename)

        build_data["shared_scripts"] = scripts
        if sys.platform == 'win32':
            build_data["pure_python"] = False
            build_data["tag"] = f"py3-none-{next(packaging.tags.sys_tags()).platform}"
        else:
            build_data["pure_python"] = False

    def finalize(
            self, version: str, build_data: typing.Dict[str, typing.Any], artifact_path: str
    ) -> None:
        self._cleanup()
        return super().finalize(version, build_data, artifact_path)

    def _cleanup(self) -> None:
        if self.__tmp_dir:
            shutil.rmtree(self.__tmp_dir, ignore_errors=True)
            self.__tmp_dir = None
