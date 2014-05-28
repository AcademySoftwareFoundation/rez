"""
Creates a wheel-based Rez distribution and installs it to the given path. This
is the development equivalent of running "python get-rez.py".
"""
import sys
import os
import os.path
import shutil
import textwrap
from optparse import OptionParser

# expose rez
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, 'src'))


def check_dependency(name, min_ver=None):
    try:
        module = __import__(name)
    except:
        print >> sys.stderr, "requires %s python module" % name
        sys.exit(1)

    if min_ver:
        try:
            nums = [int(x) for x in module.__version__.split('.')]
        except:
            nums = None
        if nums and (nums < list(min_ver)):
            print >> sys.stderr, "requires %s>=%s" \
                                 % (name, '.'.join(str(x) for x in min_ver))
            sys.exit(1)
    return module


if __name__ == "__main__":
    # check dependencies
    if sys.version_info[:2] < [2, 6]:
        print >> sys.stderr, "requires python>=2.6"
        sys.exit(1)

    pip = check_dependency("pip", (1, 5))
    check_dependency("setuptools", (0, 8))
    check_dependency("wheel")

    # parse input
    usage = "usage: %prog [options] INSTALL_PATH"
    parser = OptionParser(usage=usage)
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error("expected install path")
    install_path = os.path.abspath(os.path.expanduser(args[0]))

    # prepare - chdir, delete previous wheel, write setup.cfg
    builddir = here
    os.chdir(builddir)

    wheelhouse = os.path.join(builddir, "wheelhouse")
    if os.path.exists(wheelhouse):
        shutil.rmtree(wheelhouse)

    from rez._installer import create_setup_cfg
    content = create_setup_cfg(install_path)
    with open("setup.cfg", 'w') as f:
        f.write(content)

    # use pip to build and install
    print "building wheel..."
    ret = pip.main(["wheel", "."])
    if ret:
        sys.exit(ret)

    print "installing wheel..."
    wheelfile = os.listdir("wheelhouse")[0]
    wheelpath = os.path.join("wheelhouse", wheelfile)
    sys.exit(pip.main(["install", wheelpath]))
