__author__ = 'federicon'
__docformat__ = 'epytext'

import subprocess
import sys
import os
from rez.resolved_context import ResolvedContext
from rez.config import config


def launch_dora_from_context_file(contextFile):

    print >> sys.stdout, "Getting dora environment ..."
    rc = ResolvedContext(['dora'], package_paths=config.nonlocal_packages_path)
    doraEnvironment = rc.get_environ()
    env = dict(os.environ)
    doraCommand = '%s -i %s ' % (doraEnvironment.get('DORA_EXE'), contextFile)
    print >> sys.stdout, "Dora command: %s" % doraCommand
    env.update(doraEnvironment)
    proc = subprocess.Popen(doraCommand.split(), env=env,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)

    out, err = proc.communicate()
    if out.strip():
        print >> sys.stdout, "Dora output: (%s)" % out
    if err.strip():
        print >> sys.stderr, "Dora stderr: ", err
    proc.wait()
    returnCode = not bool(proc.returncode)
    sys.exit(returnCode)
