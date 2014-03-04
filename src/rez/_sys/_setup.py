from __future__ import with_statement
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


def _mkpkg(name, version, content=None):
    print "Creating bootstrap package: %s..." % name
    dirs = [bootstrap_path, name, version]
    _mkdirs(*dirs)
    pkg_path = os.path.join(*dirs)
    fpath = os.path.join(pkg_path, "package.py")

    content = content or textwrap.dedent( \
    """
    config_version = 0
    name = '%(name)s'
    version = '%(version)s'
    """ % dict(name=name, version=version))

    content = content.strip() + '\n'
    with open(fpath, 'w') as f:
        f.write(content)
    return pkg_path


# TODO add os dep when version submod is fixed
def _mkpythonpkg():
    version = '.'.join(str(x) for x in sys.version_info[:3])
    variant = [
        "platform-%s" % system.platform,
        "arch-%s" % system.arch]

    content = textwrap.dedent( \
    """
    config_version = 0
    name = 'python'
    version = '%(version)s'
    variants = [%(variant)s]
    def commands():
        env.PATH.append('{this.root}')
    """ % dict(
        version=version,
        variant=str(variant)))

    pkg_path = _mkpkg("python", version, content)
    root_path = _mkdirs(*([pkg_path] + variant))

    pypath = os.path.join(root_path, "python")
    os.symlink(sys.executable, pypath)


def _mkhelloworldpkg():
    version = "1.0"
    content = textwrap.dedent( \
    """
    config_version = 0
    name = 'python'
    version = '%(version)s'
    requires = ["python"]
    def commands():
        env.PATH.append('{this.root}')
    """ % dict(version=version))

    pkg_path = _mkpkg("hello_world", version, content)
    exepath = os.path.join(pkg_path, "hello_world")
    with open(exepath, 'w') as f:
        f.write(textwrap.dedent( \
        """
        #!/usr/bin/env python
        import sys
        from optparse import OptionParser

        p = OptionParser()
        p.add_option("-q", dest="quiet", action="store_true",
            help="quiet mode")
        p.add_option("-r", dest="retcode", type="int", default=0,
            help="exit with a non-zero return code")
        opts,args = p.parse_args()

        if not opts.quiet:
            print "Hello Rez World!"
        sys.exit(opts.retcode)
        """).strip())
    os.chmod(exepath, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | \
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


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
            if script.startswith('_'):
                shutil.copy(file, dst)
            else:
                if script == "rezolve":
                    code = textwrap.dedent( \
                    """
                    #!%(py_exe)s
                    __PATCH__
                    from rez.cli.main import run
                    run()
                    """ % dict(
                        py_exe=sys.executable)).strip()
                else:
                    cmd = script.split('-',1)[-1]
                    code = textwrap.dedent( \
                    """
                    #!%(py_exe)s
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
    _mkpkg("platform", system.platform)
    _mkpkg("arch", system.arch)
    _mkpkg("os", system.os)
    _mkpythonpkg()
    _mkhelloworldpkg()
