"""
Functions for bootstrapping Rez.
"""
from rez import module_root_path, __version__
from rez.util import get_script_path, get_bootstrap_path, get_rez_install_path
import os.path
import sys
import shutil



_bootstrapped = None
_in_venv = None

def is_bootstrapped():
    """Detect if Rez has been installed via rez-bootstrap cli tool."""
    global _bootstrapped
    if _bootstrapped is None:
        path = os.path.join(get_rez_install_path(), ".rez-bootstrapped")
        _bootstrapped = os.path.exists(path)
    return _bootstrapped


# TODO is this robust?
def is_in_virtualenv():
    """Detect if the current Rez install is within a virtualenv."""
    global _in_venv
    if _in_venv is None:
        import pkg_resources

        _in_venv = False
        dist = pkg_resources.get_distribution("rez")
        if os.path.isdir(dist.location):
            path,base = os.path.split(dist.location)
            if base == "site-packages":
                f1 = os.path.join(path, "orig-prefix.txt")
                f2 = os.path.join(path, "no-global-site-packages.txt")
                if os.path.isfile(f1) or os.path.isfile(f2):
                    _in_venv = True
    return _in_venv


def print_info(buf=sys.stdout):
    """
    Print information about the Rez install and if/how it has been bootstrapped.
    """
    def _pr(s=''):
        print >> buf, s

    _pr("\nRez %s @ %s\n" % (__version__, module_root_path))

    if is_bootstrapped():
        install_path = get_rez_install_path()
        path = os.path.join(install_path, ".rez-bootstrapped")
        with open(path) as f:
            init_script = f.read().strip()

        _pr("Rez has been bootstrapped into %s." % install_path)
        _pr("Sourcing %s in this directory binds Rez to the environment."
            % init_script)
    elif is_in_virtualenv():
        _pr("Rez is a standard python module, installed into a virtual env. To "
        "create a production-ready bootstrapped install, run rez-bootstrap "
        "with the --install-path option.")
    else:
        _pr("Rez is a standard python module. To create a production-ready "
            "bootstrapped install, it is highly recommended that you first "
            "install Rez into a virtualenv, and then run rez-bootstrap with "
            "the --install-path option.")
    _pr()


def install_into(path, shell=None):
    """
    Create a production-ready Rez install, in the given path. This installation
    will contain Rez itself (and dependencies) as bootstrapped Rez packages,
    and will also contain an init script, which binds this Rez install into the
    current environment.
    @param path The installation path. An init script (such as 'init.sh') will
        be created directly under this dir. The dir must not already exist,
        but its parent directory must.
    @param shell Write an init script suited to this shell. Defaults to the
        current shell.
    @returns Path to the resulting init script which, when sourced, will bind
        this instance of Rez to the current environment.
    """
    from rez.py_dist import get_dist_dependencies, convert_dist
    from rez.shells import create_shell
    from rez.rex import RexExecutor

    if os.path.exists(path):
        raise Exception("Path already exists: %s" % path)
    ppath = os.path.dirname(path)
    if not os.path.isdir(ppath):
        raise Exception("Path does not exist or is not a dir: %s" % ppath)
    os.mkdir(path)

    print "Copying bootstrap packages..."
    src = get_bootstrap_path()
    bootstrap_path = os.path.join(path, "packages")
    shutil.copytree(src, bootstrap_path)

    if is_bootstrapped():
        print "Copying binaries..."
        bin_path = get_script_path()
        dst_bin_path = os.path.join(path, "bin")
        shutil.copytree(bin_path, dst_bin_path)
    else:
        # convert rez itself, and its dependencies, into bootstrap packages.
        pkgs = get_dist_dependencies('rez')
        pypaths = []

        for pkg in pkgs:
            print "Creating bootstrap package: %s..." % pkg
            ignore = ("packages", "bin") if pkg == 'rez' else None
            dst_path = convert_dist(pkg, bootstrap_path,
                                    make_variant=False,
                                    ignore_dirs=ignore)
            pypaths.append(dst_path)

        rel_pypaths = [os.path.relpath(x, bootstrap_path) for x in pypaths]
        code_ln = "rel_pypaths = %s" % str(rel_pypaths)

        print "Copying binaries..."
        bin_path = get_script_path()
        dst_bin_path = os.path.join(path, "bin")
        os.mkdir(dst_bin_path)

        for script in os.listdir(bin_path):
            print "%s..." % script
            file = os.path.join(bin_path, script)
            if script.startswith('_'):
                shutil.copy(file, dst_bin_path)
            else:
                with open(file) as f:
                    code = f.read()
                code = code.replace("rel_pypaths=None", code_ln)
                dst_file = os.path.join(dst_bin_path, script)
                with open(dst_file, 'w') as f:
                    f.write(code)

                mode = os.stat(file).st_mode
                os.chmod(dst_file, mode)

    # create init script
    interpreter = create_shell(shell)
    ex = RexExecutor(interpreter=interpreter,
                     parent_variables=["PATH"],
                     bind_syspaths=False,
                     bind_rez=False)

    init_file = "init.%s" % interpreter.file_extension()
    init_path = os.path.join(path, init_file)
    print "Creating init script %s..." % init_file

    complete_file = "complete.%s" % interpreter.file_extension()
    p = os.path.join(bootstrap_path, "rez")
    dir_ = os.listdir(p)[0]
    p = os.path.join(p, dir_, "rez", "_sys", complete_file)
    p = os.path.abspath(p)
    if os.path.isfile(p):
        ex.source(p)

    dst_bin_path = os.path.abspath(dst_bin_path)
    ex.env.PATH.prepend(dst_bin_path)
    o = ex.get_output()

    with open(init_path, 'w') as f:
        f.write(o)

    # create the hidden bootstrap tag file
    tag_path = os.path.join(path, ".rez-bootstrapped")
    with open(tag_path, 'w') as f:
        f.write(init_file)

    return init_path
