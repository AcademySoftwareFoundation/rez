"""
Utility functions for bind modules.
"""
from rez.vendor.version.version import Version
from rez.exceptions import RezBindError
from rez.settings import settings
from rez.util import which
import subprocess
import os.path


def log(msg):
    if settings.debug("bind_modules"):
        print msg


def check_version(version, range=None):
    """Check that the found software version is within supplied range."""
    if range and version not in range:
        raise RezBindError("found version %s is not within range %s"
                           % (str(version), str(range)))


def find_exe(name, filepath=None):
    """Find an executable."""
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
    """
    if isinstance(version_arg, basestring):
        version_arg = [version_arg]
    args =[exepath] + version_arg

    log("running: %s" % ' '.join(args))
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout,stderr = p.communicate()
    if p.returncode:
        raise RezBindError("failed to execute %s: %s\n(error code %d)"
                           % (exepath, stderr, p.returncode))

    stdout = stdout.strip()
    log("extracting version from output: '%s'" % stdout)

    try:
        strver = stdout.split()[word_index]
        toks = strver.replace('.',' ').replace('-',' ').split()
        strver = '.'.join(toks[:version_rank])
        version = Version(strver)
    except Exception as e:
        raise RezBindError("failed to parse version from output '%s': %s"
                           % (stdout, str(e)))

    log("extracted version: '%s'" % str(version))
    return version
