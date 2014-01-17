from __future__ import with_statement
from rez import module_root_path
from rez.system import system
import textwrap
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


# setup.py/pip etc creates scripts outside of the module path (that may contain scripts from other
# packages), and assumes that the package site is in PYTHONPATH. Within a rez-env'd shell, we need
# to expose only Rez scripts, not other package scripts in a standard site location, and
# PYTHONPATH will not contain the site. So, we must copy the rez scripts to their own path, and
# patch their code so that they add the package site before using the rez python module.
def _patch_scripts(install_base_dir, scripts):
    # find scripts
    bin_path = None
    path = module_root_path
    while path:
        bin_path_ = os.path.join(path, 'bin')
        if os.path.isdir(bin_path_):
            test_script = os.path.join(bin_path_, 'rezolve')
            if os.path.isfile(test_script):
                bin_path = bin_path_
                break
        else:
            path = os.path.dirname(path)

    if not bin_path:
        raise Exception("Cannot find Rez cli tools")

    # copy and monkey-patch each script
    new_bin_path = os.path.join(module_root_path, "scripts")
    rel_install_base_dir = os.path.relpath(install_base_dir, new_bin_path)
    os.mkdir(new_bin_path)

    monkey_patch = textwrap.dedent( \
    """
    # START rez installer monkey patch
    import sys
    import site
    import os.path
    _script_dir = os.path.dirname(__file__)
    _install_base = os.path.join(_script_dir, '%(rel_path)s')
    _install_base = os.path.realpath(_install_base)
    site.addsitedir(_install_base)
    sys.path.insert(0, _install_base)
    # END rez installer monkey patch
    """ % dict(rel_path=rel_install_base_dir))

    for script in scripts:
        file = os.path.join(bin_path, script)
        if os.path.isfile(file):
            mode = os.stat(file).st_mode
            with open(file) as f:
                code = f.read()

            loc1 = code.split('\n')
            loc2 = monkey_patch.split('\n')
            loc = [loc1[0]] + loc2 + loc1[1:]

            patched_code = '\n'.join(loc)
            dst = os.path.join(new_bin_path, script)
            with open(dst, 'w') as f:
                f.write(patched_code)
            os.chmod(dst, mode)

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


def post_install(install_base_dir, scripts):
    script_dir = _patch_scripts(install_base_dir, scripts)
    _create_introspection_src(install_base_dir, script_dir)

    print "Creating bootstrap package: platform..."
    _mkpkg("platform", system.platform)

    print "Creating bootstrap package: arch..."
    _mkpkg("arch", system.arch)

    print "Creating bootstrap package: os..."
    _mkpkg("os", system.os)
