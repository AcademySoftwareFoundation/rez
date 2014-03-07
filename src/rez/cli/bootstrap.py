import sys
import os.path
from rez.bootstrap import print_info, install_into, is_bootstrapped, \
    is_in_virtualenv


def command(opts, parser=None):
    if opts.install_path:
        if (not opts.force) and (not is_bootstrapped()) and (not is_in_virtualenv()):
            print >> sys.stderr, \
                "Error: You are attempting to bootstrap Rez from a standard " + \
                "python install. This may fail. If it does, you should reinstall " + \
                "rez into a virtualenv, and then bootstrap from there. To go " + \
                "ahead anyway, use the --force option."
            sys.exit(1)

        init_script = install_into(opts.install_path, opts.shell)
        print
        print ("Rez has been bootstrapped into %s. To bind Rez to the current " + \
        "environment, source the file %s." % (opts.install_path, init_script))
        print
        print "Do not move this installation to another location. Instead, " + \
        "run 'rez-bootstrap --install-path=PATH' again, specifying the new " + \
        "install path."
        print
    else:
        print_info()
