from __future__ import with_statement
from rez import module_root_path
from rez.system import system
from rez.util import _mkdirs
from rez.py_dist import get_dist_dependencies, convert_dist
import textwrap
import stat
import sys
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
        print "Hello Rez World!"
        """).strip())
    os.chmod(exepath, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | \
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


# create our own scripts, located inside the rez distribution, that will work within
# an unconfigured environment (ie, PYTHONPATH may not contain Rez).
def _create_scripts(install_base_dir, install_scripts_dir, version, scripts):
    new_bin_path = os.path.join(module_root_path, "bin")
    rel_install_base_dir = os.path.relpath(install_base_dir, new_bin_path)
    os.mkdir(new_bin_path)

    patch = textwrap.dedent( \
    """
    #!%(python_exe)s
    import sys
    import site
    import os.path
    _script_dir = os.path.dirname(__file__)
    _install_base = os.path.join(_script_dir, '%(rel_path)s')
    _install_base = os.path.realpath(_install_base)
    site.addsitedir(_install_base)
    sys.path.insert(0, _install_base)
    """ % dict(
        python_exe=sys.executable,
        rel_path=rel_install_base_dir))
    patch_loc = patch.split('\n')

    for script in scripts:
        file = os.path.join(install_scripts_dir, script)
        if os.path.isfile(file):
            mode = os.stat(file).st_mode
            with open(file) as f:
                code = f.read()

            loc = code.split('\n')
            shebang = loc[0]
            loc = patch_loc + loc[1:]

            # only patch python scripts, others are unchanged
            is_python = ("python" in shebang.lower())
            patched_code = '\n'.join(loc).strip() if is_python else code

            dst = os.path.join(new_bin_path, script)
            with open(dst, 'w') as f:
                f.write(patched_code)
            os.chmod(dst, mode)

    return new_bin_path


def post_install(install_base_dir, install_scripts_dir, version, scripts):
    # create bootstrap packages
    _mkpkg("platform", system.platform)
    _mkpkg("arch", system.arch)
    _mkpkg("os", system.os)
    _mkpythonpkg()
    _mkhelloworldpkg()

    # convert rez itself, and its dependencies, into bootstrap packages
    pkgs = get_dist_dependencies('rez')
    pypaths = []

    for pkg in pkgs:
        print "Creating bootstrap package: %s..." % pkg
        sys.stdout.flush()
        path = convert_dist(pkg, bootstrap_path, make_variant=False)
        pypaths.append(path)

    # create patched scripts
    script_dir = _create_scripts(install_base_dir, install_scripts_dir,
                                 version, scripts)
