'''
Rez installation-related operations.
'''
import sys

def setup_parser(parser):
    from rez.shells import get_shell_types
    from rez.system import system
    shells = get_shell_types()
    parser.add_argument("--install-path", dest="install_path", type=str,
                        help="create a bootstrapped install of Rez in the "
                        "given path")
    parser.add_argument("--sh", "--shell", dest="shell", type=str, choices=shells,
                        help="target shell type of the install, defaults to the "
                        "current shell (%s)" % system.shell)
    parser.add_argument("--force", action="store_true",
                        help="create a bootstrapped Rez install, even if "
                        "advised not to")

def command(opts, parser=None):
    from rez.bootstrap import print_info, install_into, is_bootstrapped, \
        is_in_virtualenv

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
        "environment, source the file %s.") % (opts.install_path, init_script)
        print
        print "Do not move this installation to another location. Instead, " + \
        "run 'rez-bootstrap --install-path=PATH' again, specifying the new " + \
        "install path."
        print
    else:
        print_info()
