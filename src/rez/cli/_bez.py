from __future__ import print_function

import os
import sys
import os.path
import textwrap
import subprocess
import argparse
from rez.vendor import yaml
from rez.utils.execution import Popen
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
            print("no %s file found. Stop." % file, file=sys.stderr)
            sys.exit(1)

    with open(".bez.yaml") as f:
        doc = yaml.load(f.read(), Loader=yaml.FullLoader)

    source_path = doc["source_path"]
    buildfile = os.path.join(source_path, "rezbuild.py")
    if not os.path.isfile(buildfile):
        print("no rezbuild.py at %s. Stop." % source_path, file=sys.stderr)
        sys.exit(1)

    # run rezbuild.py:build() in python subprocess. Cannot import module here
    # because we're in a python env configured for rez, not the build
    code = \
    """
    env={}
    with open("%(buildfile)s") as stream:
        exec(compile(stream.read(), stream.name, 'exec'), env)

    buildfunc = env.get("build")
    if not buildfunc:
        import sys
        sys.stderr.write("Did not find function 'build' in rezbuild.py\\n")
        sys.exit(1)

    kwargs = dict(source_path="%(srcpath)s",
                  build_path="%(bldpath)s",
                  install_path="%(instpath)s",
                  targets=%(targets)s,
                  build_args=%(build_args)s)

    import inspect

    if hasattr(inspect, "getfullargspec"):
        # support py3 kw-only args
        spec = inspect.getfullargspec(buildfunc)
        args = spec.args + spec.kwonlyargs
    else:
        args = inspect.getargspec(buildfunc).args

    kwargs = dict((k, v) for k, v in kwargs.items() if k in args)

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

    print("executing rezbuild.py...")
    cmd = [sys.executable, bezfile]

    with Popen(cmd) as p:
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
