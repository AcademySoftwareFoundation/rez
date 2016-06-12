"""
Utility functions for bind modules.
"""
from __future__ import absolute_import
from rez.vendor.version.version import Version
from rez.exceptions import RezBindError
from rez.config import config
from rez.util import which
from rez.utils.logging_ import print_debug
import subprocess
import os.path
import os


def log(msg):
    if config.debug("bind_modules"):
        print_debug(msg)


def make_dirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


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
            open(filepath)  # raise IOError
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

    log("running: %s" % ' '.join(args))
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode:
        raise RezBindError("failed to execute %s: %s\n(error code %d)"
                           % (exepath, stderr, p.returncode))

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


# Copyright 2016 Allan Johns.
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
