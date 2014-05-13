import os
import sys
import imp
import argparse
import os.path
import inspect
from rez.vendor import yaml
from rez.resolved_context import ResolvedContext



def run():
    parser = argparse.ArgumentParser( \
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

    # get build function object in rezbuild.py
    stream = open(buildfile)
    namespace = {}
    exec stream in namespace

    buildfunc = namespace.get("build")
    if not buildfunc:
        print >> sys.stderr, "rezbuild.py has no 'build' function"
        sys.exit(1)

    if not inspect.isfunction(buildfunc):
        print >> sys.stderr, "build (in rezbuild.py) is not a function"
        sys.exit(1)

    # create context to pass to build()
    r = ResolvedContext.load("build.rxt")

    print "executing rezbuild.py..."
    buildfunc(context=r,
              source_path=source_path,
              build_path=doc["build_path"],
              install_path=doc["install_path"],
              targets=opts.TARGET or None)
