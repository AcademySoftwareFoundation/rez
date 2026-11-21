# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Check actual Windows pip/uv wheel placement and -script.py(w) execution."""

# Standalone CI script, not an importable package.
# ruff: noqa: INP001

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def run(*args, **kwargs):
    result = subprocess.run(args, check=False, text=True, capture_output=True, timeout=90, **kwargs)
    assert result.returncode == 0, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    options = parser.parse_args()
    wheel = options.wheel.resolve()

    # Check the wheel layout and Windows executable types before installation.
    with ZipFile(wheel) as archive:
        scripts = {Path(name).name: archive.read(name) for name in archive.namelist() if ".data/scripts/" in name}
        native = {
            Path(name).name: archive.read(name) for name in archive.namelist() if ".data/data/Scripts/rez/" in name
        }

        assert {name.rsplit("-script.", 1)[0] + ".exe" for name in scripts} == set(native)
        assert {
            "rez.exe",
            "rez-env.exe",
            "rez-gui.exe",
            "_rez-install-test.exe",
        } <= set(native)
        assert all(
            "/" not in name.split(".data/scripts/", 1)[1] for name in archive.namelist() if ".data/scripts/" in name
        )
        assert "rez-gui-script.pyw" in scripts and "rez-gui-script.py" not in scripts
        assert all(value.startswith(b"#!python\n") for value in scripts.values())

        for name, subsystem in [("rez.exe", 3), ("rez-gui.exe", 2)]:
            data = native[name]
            pe = struct.unpack_from("<I", data, 0x3C)[0]
            assert struct.unpack_from("<H", data, pe + 24 + 68)[0] == subsystem

    # Try both installers with plain paths and paths containing spaces and a quote.
    with TemporaryDirectory(prefix="rez-wheel-") as temp:
        root = Path(temp)
        for installer in ["pip", "uv"]:
            for name in ["plain", "space and ' quote"]:
                venv = root / (installer + "-" + name)
                run(sys.executable, "-m", "venv", venv)
                python = venv / "Scripts/python.exe"
                if installer == "pip":
                    run(python, "-m", "pip", "install", "--no-deps", wheel)
                else:
                    run("uv", "pip", "install", "--python", python, "--no-deps", wheel)

                # Verify installed .exe bytes and rewritten -script.py(w) shebangs.
                commands = venv / "Scripts/rez"
                assert {path.name for path in commands.iterdir()} == set(native)
                for filename, data in native.items():
                    assert (commands / filename).read_bytes() == data
                for filename in scripts:
                    header = (venv / "Scripts" / filename).read_bytes().splitlines()[0]
                    assert header.startswith(b"#!") and b"python.exe" in header, header
                    assert os.fsencode(str(venv)).lower() in header.lower(), header

                # Keep the venv's Python off PATH; check isolation and arguments.
                env = dict(
                    os.environ,
                    PATH=str(commands) + os.pathsep + os.environ["PATH"],
                    PYTHONHOME="Z:\\no-such-python-home",
                    PYTHONPATH="Z:\\no-such-python-path",
                )
                assert str(venv / "Scripts") not in env["PATH"].split(os.pathsep)
                assert run("cmd", "/d", "/c", "rez", "--version", env=env).startswith("Rez ")
                args = ["", "hello world", "literal ' \" $*", "--"]
                result = json.loads(run(commands / "_rez-install-test.exe", *args, env=env))
                assert result["argv"][1:] == args, result
                assert os.path.normcase(result["executable"]) == os.path.normcase(str(python)), result
                assert result["sysflags"]["ignore_environment"] == 1, result

                # Accept .EXE, but reject other endings before -script.py(w) lookup.
                uppercase = commands / "rez-case.EXE"
                uppercase.write_bytes(native["rez.exe"])
                uppercase_script = venv / "Scripts/rez-case-script.py"
                uppercase_script.write_bytes((venv / "Scripts/rez-script.py").read_bytes())
                assert run(uppercase, "--version", env=env).startswith("Rez ")
                uppercase.unlink()
                uppercase_script.unlink()

                for filename in ["rez.com", "rez.exe.com", "rez-no-extension"]:
                    renamed = commands / filename
                    renamed.write_bytes(native["rez.exe"])
                    result = subprocess.run(
                        [renamed, "--version"],
                        executable=renamed,
                        env=env,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    renamed.unlink()
                    assert result.returncode == 1 and not result.stdout, result
                    assert "Executable filename must end in '.exe'" in result.stderr, result.stderr

                # A GUI payload writes to a file, independent of console availability.
                script = venv / "Scripts/rez-gui-script.pyw"
                binding = script.read_bytes().splitlines(keepends=True)[0]
                output = venv / "gui.json"
                script.write_bytes(
                    binding
                    + (
                        "import json, sys\nfrom pathlib import Path\n"
                        f"Path({str(output)!r}).write_text(json.dumps([sys.executable, "
                        "sys.flags.ignore_environment, sys.argv[1:]]))\n"
                    ).encode()
                )
                run(commands / "rez-gui.exe", *args, env=env)
                executable, isolated, argv = json.loads(output.read_text())
                assert os.path.normcase(executable) == os.path.normcase(str(python))
                assert isolated == 1 and argv == args

                print(f"PASS Windows {installer}: {name}, flat -script.py(w) files, native data, CLI/GUI, argv, -E")


if __name__ == "__main__":
    main()
