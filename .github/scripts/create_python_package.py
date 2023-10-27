import os
import zipfile
import argparse
import platform
import tempfile
import subprocess
import urllib.request

import rez.packages
import rez.package_maker


parser = argparse.ArgumentParser()
parser.add_argument("version", help="Python version")
parser.add_argument("repository", help="Repository path")

args = parser.parse_args()


def make_root(variant: rez.packages.Variant, path: str):
    dest = os.path.join(path, "python")

    if platform.system() == "Windows":
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, "python.nupkg")

            url = f"https://globalcdn.nuget.org/packages/python.{variant.version}.nupkg"

            print(f"Downloading {url!r}")
            with urllib.request.urlopen(url) as archive:
                with open(archive_path, "wb") as targetFile:
                    targetFile.write(archive.read())

            with zipfile.ZipFile(archive_path) as archive:
                print(f"Extracting {archive_path!r} to {dest!r}")
                archive.extractall(path=dest)
    else:
        cmd = [
            "conda",
            "create",
            "--prefix",
            dest,
            f"python={args.version}",
            "pip",
            "--yes",
        ]
        print(f"Running {' '.join(cmd)!r}")
        subprocess.check_call(cmd)


with rez.package_maker.make_package(
    "python", os.path.expanduser(args.repository), make_root=make_root
) as package:
    package.version = args.version
    commands = [
        "env.PATH.prepend('{root}/python/bin')",
    ]
    if platform.system() == "Windows":
        commands = [
            "env.PATH.prepend('{root}/python/tools')",
            "env.PATH.prepend('{root}/python/tools/DLLs')",
        ]

    package.commands = "\n".join(commands)
