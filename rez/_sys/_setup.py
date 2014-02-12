from __future__ import with_statement
from rez import module_root_path
from rez.system import system
import textwrap
import stat
import sys
import os
import os.path


try:
    assert(os.environ.get("__rez_is_installing"))
except:
    raise Exception("do not import _setup.py")


def _mkdirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)


def _mkpkg(name, version, content=None):
    dirs = [module_root_path, "packages", name, version]
    _mkdirs(*dirs)
    fpath = os.path.join(*(dirs + ["package.yaml"]))
    with open(fpath, 'w') as f:
        content = content or textwrap.dedent( \
        """
        config_version: 0
        name: %(name)s
        version: %(version)s
        """ % dict(name=name, version=version))
        f.write(content)


# create our own scripts, located inside the rez distribution, that will work within
# an unconfigured environment (ie, PYTHONPATH may not contain Rez).
def _create_scripts(install_base_dir, version, scripts):
    new_bin_path = os.path.join(module_root_path, "scripts")
    rel_install_base_dir = os.path.relpath(install_base_dir, new_bin_path)
    os.mkdir(new_bin_path)

    code = textwrap.dedent( \
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

    __requires__ = 'rez==%(version)s'
    import pkg_resources
    pkg_resources.run_script('rez==%(version)s', '%(script_name)s')
    """).strip()

    for script in scripts:
        fpath = os.path.join(new_bin_path, script)
        contents = code % dict(
            python_exe=sys.executable,
            rel_path=rel_install_base_dir,
            version=version,
            script_name=script)
        with open(fpath, 'w') as f:
            f.write(contents)

        os.chmod(fpath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH \
            | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return new_bin_path


# this trickery is needed so that the rezolve script can patch the python environment
# when inside a rev-env'd shell, so that rez can operate correctly.
def _create_introspection_src(install_base_dir, script_dir):
    path = os.path.join(module_root_path, "_sys", "_introspect.py")
    with open(path, 'w') as f:
        relpath = os.path.relpath(install_base_dir, module_root_path)
        f.write("_install_site_path = '%s'\n" % relpath)

        relpath = os.path.relpath(script_dir, module_root_path)
        f.write("_script_path = '%s'\n" % relpath)


def post_install(install_base_dir, version, scripts):
    script_dir = _create_scripts(install_base_dir, version, scripts)
    _create_introspection_src(install_base_dir, script_dir)

    print "Creating bootstrap package: platform..."
    _mkpkg("platform", system.platform)

    print "Creating bootstrap package: arch..."
    _mkpkg("arch", system.arch)

    print "Creating bootstrap package: os..."
    _mkpkg("os", system.os)
