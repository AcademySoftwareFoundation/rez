"""
Utility functions for bind modules.
"""
from __future__ import absolute_import
from rez.vendor.version.version import Version
from rez.exceptions import RezBindError
from rez.config import config
from rez.util import which
from rez.utils.execution import Popen
from rez.utils.logging_ import print_debug
from rez.vendor.six import six
from pipes import quote
import subprocess
import os.path
import os
import platform
import sys


basestring = six.string_types[0]


def log(msg):
    if config.debug("bind_modules"):
        print_debug(msg)


def make_dirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def run_python_command(commands, exe=None):
    py_cmd = "; ".join(commands)
    args = [exe or sys.executable, "-c", py_cmd]
    stdout, stderr, returncode = _run_command(args)
    return (returncode == 0), stdout.strip(), stderr.strip()


def get_version_in_python(name, commands):
    success, out, err = run_python_command(commands)
    if not success or not out:
        raise RezBindError("Couldn't determine version of module %s: %s"
                           % (name, err))
    version = out
    return version


def check_version(version, range_=None):
    """Check that the found software version is within supplied range.

    Args:
        version: Version of the package as a Version object.
        range_: Allowable version range as a VersionRange object.
    """
    if range_ and version not in range_:
        raise RezBindError("found version %s is not within range %s"
                           % (str(version), str(range_)))


def find_exe(name, filepath=None):
    """Find an executable.

    Args:
        name: Name of the program, eg 'python'.
        filepath: Path to executable, a search is performed if None.

    Returns:
        Path to the executable if found, otherwise an error is raised.
    """
    if filepath:
        if not os.path.exists(filepath):
            with open(filepath):
                pass  # raise IOError
        elif not os.path.isfile(filepath):
            raise RezBindError("not a file: %s" % filepath)
    else:
        filepath = which(name)
        if not filepath:
            raise RezBindError("could not find executable: %s" % name)

    return filepath


def extract_version(exepath, version_arg, word_index=-1, version_rank=3):
    """Run an executable and get the program version.

    Args:
        exepath: Filepath to executable.
        version_arg: Arg to pass to program, eg "-V". Can also be a list.
        word_index: Expect the Nth word of output to be the version.
        version_rank: Cap the version to this many tokens.

    Returns:
        `Version` object.
    """
    if isinstance(version_arg, basestring):
        version_arg = [version_arg]
    args = [exepath] + version_arg

    stdout, stderr, returncode = _run_command(args)
    if returncode:
        raise RezBindError("failed to execute %s: %s\n(error code %d)"
                           % (exepath, stderr, returncode))

    stdout = stdout.strip().split('\n')[0].strip()
    log("extracting version from output: '%s'" % stdout)

    try:
        strver = stdout.split()[word_index]
        toks = strver.replace('.', ' ').replace('-', ' ').split()
        strver = '.'.join(toks[:version_rank])
        version = Version(strver)
    except Exception as e:
        raise RezBindError("failed to parse version from output '%s': %s"
                           % (stdout, str(e)))

    log("extracted version: '%s'" % str(version))
    return version


def _run_command(args):
    cmd_str = ' '.join(quote(x) for x in args)
    log("running: %s" % cmd_str)

    # https://github.com/nerdvegas/rez/pull/659
    use_shell = ("Windows" in platform.system())

    p = Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=use_shell,
        text=True
    )

    stdout, stderr = p.communicate()
    return stdout, stderr, p.returncode


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
