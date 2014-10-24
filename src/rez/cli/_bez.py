import os
import sys
import os.path
import textwrap
import subprocess
from rez.vendor import yaml, argparse


def run():
    parser = argparse.ArgumentParser(
        description="Simple builtin Rez build system")

    parser.add_argument("TARGET", type=str, nargs='*',
                        help="build targets")

    opts = parser.parse_args()

    # check necessary files, load info about the build
    for file in ("build.rxt", ".bez.yaml"):
        if not os.path.isfile(file):
            print >> sys.stderr, "no %s file found. Stop." % file
            sys.exit(1)

    with open(".bez.yaml") as f:
        doc = yaml.load(f.read())

    source_path = doc["source_path"]
    buildfile = os.path.join(source_path, "rezbuild.py")
    if not os.path.isfile(buildfile):
        print >> sys.stderr, "no rezbuild.py at %s. Stop." % source_path
        sys.exit(1)

    # run rezbuild.py:build() in python subprocess. Cannot import module here
    # because we're in a python env configured for rez, not the build
    code = \
    """
    stream=open("%(buildfile)s")
    env={}
    exec stream in env
    env["build"]("%(srcpath)s","%(bldpath)s","%(instpath)s",%(targets)s)
    """ % dict(buildfile=buildfile,
               srcpath=source_path,
               bldpath=doc["build_path"],
               instpath=doc["install_path"],
               targets=str(opts.TARGET or None))

    cli_code = textwrap.dedent(code).strip().replace('\n', ';')

    print "executing rezbuild.py..."
    cmd = ["python", "-c", cli_code]
    p = subprocess.Popen(cmd)
    p.wait()
    sys.exit(p.returncode)
