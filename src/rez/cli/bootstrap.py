from rez.bootstrap import print_info, install_into


def command(opts, parser=None):
    if opts.install_path:
        init_script = install_into(opts.install_path, opts.shell)
        print
        print ("Rez has been packaged into a self-contained installation. To " + \
        "bind Rez to the current environment, source the file %s.") % init_script
        print
        print "Do not move this installation to another location. Instead, " + \
        "run 'rez-bootstrap --install-path=PATH' again, specifying the new " + \
        "install path."
        print
    else:
        print_info()
