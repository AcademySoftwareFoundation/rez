import os
import tarfile
import argparse
import platform
import urllib.request

import rez.packages
import rez.package_maker


parser = argparse.ArgumentParser()
parser.add_argument("version", help="Python version")
parser.add_argument("repository", help="Repository path")

args = parser.parse_args()


INTERPRETERS = {
    ("Windows", "AMD64"): "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-{version}+20240415-x86_64-pc-windows-msvc-install_only.tar.gz",
    ("Linux", "x86_64"): "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-{version}+20240415-x86_64-unknown-linux-gnu-install_only.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-{version}+20240415-x86_64-apple-darwin-install_only.tar.gz",
}

def make_root(variant: rez.packages.Variant, path: str):
    url = INTERPRETERS[(platform.system(), platform.machine())]

    print(f"Downloading {url!r} and extracting to {path!r}")
    with urllib.request.urlopen(url.format(version=variant.version)) as response:
        tar = tarfile.open(fileobj=response, mode="r:gz")
        tar.extractall(path=path)


with rez.package_maker.make_package(
    "python", os.path.expanduser(args.repository), make_root=make_root
) as package:
    package.version = args.version
    commands = [
        "env.PATH.prepend('{root}/python/bin')",
    ]
    if platform.system() == "Windows":
        commands = [
            "env.PATH.prepend('{root}/python')",
            "env.PATH.prepend('{root}/python/DLLs')",
        ]

    package.commands = "\n".join(commands)
