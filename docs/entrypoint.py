# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import argparse
import os
import site
import subprocess
import tempfile


THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
REZ_SOURCE_DIR = os.getenv("REZ_SOURCE_DIR", os.path.dirname(THIS_DIR))
REQUIREMENTS = ['sphinx-argparse', 'sphinx_rtd_theme', REZ_SOURCE_DIR]
DEST_DIR = os.path.join("docs", "_build")


class CliParser(argparse.ArgumentParser):
    """Parser flags, using global variables as defaults."""
    INIT_DEFAULTS = {
        "prog": "entrypoint",
        "description": "Build Sphinx Python API docs",
    }

    def __init__(self, **kwargs):
        """Setup default arguments and parser description/program name.

        If no parser description/program name are given, default ones will
        be assigned.

        Args:
            kwargs (dict[str]):
                Same key word arguments taken by
                ``argparse.ArgumentParser.__init__()``
        """
        for key, value in self.INIT_DEFAULTS.items():
            kwargs.setdefault(key, value)
        super(CliParser, self).__init__(**kwargs)

        self.add_argument(
            "--no-docker",
            action="store_false",
            dest="docker",
            help="Don't run build processes inside Docker container.",
        )
        self.add_argument(
            "requirement",
            nargs="*",
            help="Additional packages to pip install.",
        )


def construct_docker_run_args():
    """Create subprocess arguments list for running this script inside docker.

    Returns:
        list[str]: Arguments list for ``subprocess.call()``.
    """
    docker_args = ["docker", "run", "--interactive", "--rm"]

    if os.sys.stdin.isatty() and os.sys.stdout.isatty():
        docker_args.append("--tty")

    if os.name == "posix":
        user_group_ids = os.getuid(), os.getgid()
        docker_args += ["--user", ":".join(map(str, user_group_ids))]

    docker_args += [
        "--workdir", REZ_SOURCE_DIR,
        "--volume", ":".join([REZ_SOURCE_DIR, REZ_SOURCE_DIR]),
        "python:{v.major}.{v.minor}".format(v=os.sys.version_info),
        "python", THIS_FILE, "--no-docker"
    ]

    return docker_args


def setup_env(env=os.environ):
    """Setup environment dictionary for installing and building docs.

    Args:
        env (dict): Optional environment variables dictionary to start from.

    Returns:
        dict[str]: Copy of the modified environment variables mapping.
    """
    env = env.copy()
    home_dir = os.path.expanduser("~")
    user_base = site.getuserbase()

    if os.name == "posix" and os.path.expanduser("~") == "/":
        home_dir = tempfile.mkdtemp()
        user_base = os.path.join(home_dir, user_base.lstrip(os.sep))
        env['HOME'] = home_dir

    user_bin = os.path.join(user_base, 'bin')
    env['PATH'] += str(os.pathsep + user_bin)
    return env


def _cli():
    """Main routine for when called from command line."""
    args = CliParser().parse_args()

    if args.docker:
        docker_args = construct_docker_run_args() + args.requirement
        print('Calling "{}"'.format(subprocess.list2cmdline(docker_args)))
        os.sys.exit(subprocess.call(docker_args))
    else:
        docs_env = setup_env()
        for key, value in sorted(docs_env.items()):
            print(key, type(value), value)

        build_commands = (
            ['pip', 'install', '--user'] + REQUIREMENTS + args.requirement,
            ('sphinx-build', 'docs', DEST_DIR),
        )
        for command_args in build_commands:
            print('Calling "{}"'.format(subprocess.list2cmdline(command_args)))
            subprocess.check_call(command_args, env=docs_env)


if __name__ == "__main__":
    _cli()
