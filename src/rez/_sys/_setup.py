from rez import module_root_path
from rez.system import system
from rez.util import _mkdirs
import textwrap
import stat
import sys
import shutil
import os
import os.path



try:
    assert(os.environ.get("__rez_is_installing"))
except:
    raise Exception("do not import _setup.py")

bootstrap_path = os.path.join(module_root_path, "packages")


def _create_scripts(install_base_dir, install_scripts_dir, scripts):
    new_bin_path = os.path.join(module_root_path, "bin")
    rel_install_base_dir = os.path.relpath(install_base_dir, new_bin_path)
    os.mkdir(new_bin_path)

    patch = textwrap.dedent( \
    """
    import sys
    import os.path

    rel_pypaths=None ### !!!DO NOT CHANGE THIS LINE OF CODE!!!

    if rel_pypaths:
        p = os.path.join(os.path.dirname(__file__), "..", "packages")
        bootpaths = [os.path.realpath(os.path.join(p,x)) for x in rel_pypaths]
        sys.path = bootpaths + sys.path
    else:
        import site
        _script_dir = os.path.dirname(__file__)
        _install_base = os.path.join(_script_dir, '%(rel_path)s')
        _install_base = os.path.realpath(_install_base)
        site.addsitedir(_install_base)
        sys.path.insert(0, _install_base)
    """ % dict(
        rel_path=rel_install_base_dir)).strip()

    for script in scripts:
        file = os.path.join(install_scripts_dir, script)
        dst = os.path.join(new_bin_path, script)

        if os.path.isfile(file):
            if script in ("_rez_csh_complete",):
                shutil.copy(file, dst)
            else:
                if script == "rezolve":
                    code = textwrap.dedent( \
                    """
                    #!%(py_exe)s -E
                    __PATCH__
                    from rez.cli._main import run
                    run()
                    """ % dict(
                        py_exe=sys.executable)).strip()
                elif script == "bez":
                    code = textwrap.dedent( \
                    """
                    #!%(py_exe)s -E
                    __PATCH__
                    from rez.cli._bez import run
                    run()
                    """ % dict(
                        py_exe=sys.executable)).strip()
                else:
                    cmd = "forward" if script == "_rez_fwd" \
                        else script.split('-',1)[-1]

                    code = textwrap.dedent( \
                    """
                    #!%(py_exe)s -E
                    __PATCH__
                    from rez._sys import _forward_script
                    _forward_script('%(cmd)s')
                    """ % dict(
                        py_exe=sys.executable,
                        cmd=cmd)).strip()

                code = code.replace("__PATCH__", patch)
                mode = os.stat(file).st_mode
                with open(dst, 'w') as f:
                    f.write(code + '\n')
                os.chmod(dst, mode)


def post_install(install_base_dir, install_scripts_dir, scripts):
    # create patched scripts
    _create_scripts(install_base_dir, install_scripts_dir, scripts)

    # create bootstrap packages
    def _bind(name):
        from rez.backport.importlib import import_module
        module = import_module("rez.bind.%s" % name)
        print "creating bootstrap package for %s..." % name
        try:
            module.bind(bootstrap_path)
        except Exception as e:
            print >> sys.stderr, "Failed making package: %s" % str(e)

    _bind("platform")
    _bind("arch")
    _bind("os")
    _bind("python")
    _bind("hello_world")
