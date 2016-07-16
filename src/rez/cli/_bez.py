import os
import sys
import os.path
import textwrap
import subprocess
from rez.vendor import yaml, argparse
from rez.utils.filesystem import TempDirs
from rez.config import config


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

    # run rezbuild.py:build() in python subprocess. Cannot import module here
    # because we're in a python env configured for rez, not the build
    code = \
    """
    stream=open("%(buildfile)s")
    env={}
    exec stream in env

    buildfunc = env.get("build")
    if not buildfunc:
        import sys
        print >> sys.stderr, "Did not find function 'build' in rezbuild.py"
        sys.exit(1)

    kwargs = dict(source_path="%(srcpath)s",
                  build_path="%(bldpath)s",
                  install_path="%(instpath)s",
                  targets=%(targets)s,
                  build_args=%(build_args)s)

    import inspect
    args = inspect.getargspec(buildfunc).args
    kwargs = dict((k, v) for k, v in kwargs.iteritems() if k in args)

    buildfunc(**kwargs)

    """ % dict(buildfile=buildfile,
               srcpath=source_path,
               bldpath=doc["build_path"],
               instpath=doc["install_path"],
               targets=str(opts.TARGET or None),
               build_args=str(doc.get("build_args") or []))

    cli_code = textwrap.dedent(code).replace("\\", "\\\\")

    tmpdir_manager = TempDirs(config.tmpdir, prefix="bez_")
    bezfile = os.path.join(tmpdir_manager.mkdtemp(), "bezfile")
    with open(bezfile, "w") as fd:
        fd.write(cli_code)

    print "executing rezbuild.py..."
    cmd = ["python", bezfile]
    p = subprocess.Popen(cmd)
    p.wait()
    tmpdir_manager.clear()
    sys.exit(p.returncode)


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
