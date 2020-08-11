# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import argparse
import errno
import os
import re
import subprocess
import tempfile


THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
REZ_SOURCE_DIR = os.getenv("REZ_SOURCE_DIR", os.path.dirname(THIS_DIR))
REQUIREMENTS = ['sphinx_rtd_theme', REZ_SOURCE_DIR]
DEST_DIR = os.path.join("docs", "_build")
PIP_PATH_REGEX = re.compile(r"'([^']+)' which is not on PATH.")


class CliParser(argparse.ArgumentParser):
    """Parser flags, using global variables as defaults."""
    INIT_DEFAULTS = {
        "prog": "build",
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


def print_call(cmdline_args, *print_args, **print_kwargs):
    """Print command line call for given arguments.


    Args:
        cmdline_args (list): Command line arguments to print for.
        print_args (dict): Additional arguments for print function.
        print_kwargs (dict): Keyword arguments for print function.
    """
    width = os.getenv('COLUMNS', 80)
    out_file = print_kwargs.setdefault('file', os.sys.stdout)
    message = '{:=^{width}}{nl}{}{nl:=<{width}}'.format(
        " Calling ",
        subprocess.list2cmdline(cmdline_args),
        nl=os.linesep,
        width=width
    )
    print(message, *print_args, **print_kwargs)
    out_file.flush()


def path_with_pip_scripts(install_stderr, path_env=None):
    """Create new PATH variable with missing pip scripts paths added to it.

    Args:
        install_stderr (str): stderr output from pip install command.
        path_env (str): Custom PATH env value to start off with.

    Returns:
        str: New PATH variable value.
    """
    if path_env is None:
        path_env = os.getenv('PATH', '')
    paths = path_env.split(os.pathsep)

    for match in PIP_PATH_REGEX.finditer(install_stderr):
        script_path = match.group(1)
        if script_path not in paths:
            paths.append(script_path)

    return os.pathsep.join(paths)


def _cli():
    """Main routine for when called from command line."""
    args = CliParser().parse_args()

    if args.docker:
        docker_args = construct_docker_run_args() + args.requirement
        print_call(docker_args)
        os.sys.exit(subprocess.call(docker_args))
    else:
        docs_env = os.environ.copy()

        # Fake user's $HOME in container to fix permission issues
        if os.name == "posix" and os.path.expanduser("~") == "/":
            docs_env['HOME'] = tempfile.mkdtemp()

        # Run pip install for required docs building packages
        pip_args = ['pip', 'install', '--user']
        pip_args += REQUIREMENTS + args.requirement
        with tempfile.TemporaryFile() as stderr_file:
            subprocess.check_call(pip_args, env=docs_env, stderr=stderr_file)
            stderr_file.seek(0)
            stderr = str(stderr_file.read())
        docs_env['PATH'] = path_with_pip_scripts(stderr)

        # Run sphinx-build docs, falling back to use sphinx-build.exe
        sphinx_build = 'sphinx-build'
        build_args = ['docs', DEST_DIR]
        sphinx_build_args = [sphinx_build] + build_args
        try:
            print_call(sphinx_build_args)
            os.sys.exit(subprocess.call(sphinx_build_args, env=docs_env))
        except OSError as error:
            if error.errno == errno.ENOENT:
                # Windows Py2.7 needs full .exe path, see GitHub workflows run:
                # https://github.com/wwfxuk/rez/runs/380399547
                latest_path = docs_env['PATH'].split(os.pathsep)[-1]
                sphinx_build = os.path.join(latest_path, sphinx_build + '.exe')

                sphinx_build_args = [sphinx_build] + build_args
                print_call(sphinx_build_args)
                os.sys.exit(subprocess.call(sphinx_build_args, env=docs_env))
            else:
                raise


if __name__ == "__main__":
    _cli()
