'''
Set a timestamp on a package.

Creating a timestamp file ensures that the package works correctly with rez's
timestamping feature (see the user manual). If a package is not timestamped then rez
treats it as though it does not exist.
'''
from __future__ import with_statement
import os.path
import sys
from rez.cli import error, output


def setup_parser(parser):
    parser.add_argument("path", default=".", nargs="?")

def command(opts, parser=None):
    yamlpath = os.path.join(opts.path, "package.yaml")
    if not os.path.exists(yamlpath):
        print>>sys.stderr, "Error: Target package does not contain a package.yaml file."
        sys.exit(1)

    metapath = os.path.join(opts.path, ".metadata")
    timepath = os.path.join(metapath, "release_time.txt")

    if os.path.exists(timepath):
        error("Target package is already timestamped: %s" % timepath)
        sys.exit(1)

    if not os.path.exists(metapath):
        try:
            os.mkdir(metapath)
        except Exception, err:
            error("Could not create dir: %s: %s" % (metapath, str(err)))

    import time
    with open(timepath, 'w') as f:
        f.write(str(int(time.time())))

    from rez.util import remove_write_perms
    remove_write_perms(timepath)
    print "Success: Package has been timestamped. See %s" % timepath
