"""
Binds a python module to rez.

Note that we subproc out to python at various points here because we can't use
the current python interpreter - this is rez's, inside its installation
virtualenv.
"""
from __future__ import absolute_import, print_function

from rez.bind._utils import check_version, find_exe, make_dirs, \
    get_version_in_python, run_python_command, log
from rez.package_maker__ import make_package
from rez.exceptions import RezBindError
from rez.system import system
from rez.utils.logging_ import print_warning
import subprocess
import shutil
import sys
import os.path


def commands():
    env.PYTHONPATH.append('{this.root}/python')


def commands_with_bin():
    env.PYTHONPATH.append('{this.root}/python')
    env.PATH.append('{this.root}/bin')


def copy_module(name, destpath):
    success, out, err = run_python_command(
        ["import %s" % name,
         "print(%s.__path__[0] if hasattr(%s, '__path__') else '')" % (name, name)])

    if out:
        srcpath = out
        shutil.copytree(srcpath, os.path.join(destpath, name))
    else:
        success, out, err = run_python_command(
            ["import %s" % name,
             "print(%s.__file__)" % name])
        if not success:
            raise RezBindError("Couldn't locate module %s: %s" % (name, err))

        srcfile = out
        dirpart, ext = os.path.splitext(srcfile)

        if ext == ".pyc":
            pyfile = dirpart + ".py"
            if os.path.exists(pyfile):
                srcfile = pyfile

        destfile = os.path.join(destpath, os.path.basename(srcfile))
        shutil.copy2(srcfile, destfile)


def bind(name, path, import_name=None, version_range=None, version=None,
         requires=None, pure_python=None, tools=None, extra_module_names=[],
         extra_attrs={}):
    import_name = import_name or name

    if version is None:
        version = get_version_in_python(
            name,
            ["import %s" % import_name,
             "print(%s.__version__)" % import_name])

    check_version(version, version_range)

    py_major_minor = '.'.join(str(x) for x in sys.version_info[:2])
    py_req = "python-%s" % py_major_minor
    found_tools = {}

    if pure_python is None:
        raise NotImplementedError  # detect
    elif pure_python:
        variant = [py_req]
    else:
        variant = system.variant + [py_req]

    for tool in (tools or []):
        try:
            src = find_exe(tool)
            found_tools[tool] = src
            log("found tool '%s': %s" % (tool, src))
        except RezBindError as e:
            print_warning(str(e))

    def make_root(variant, root):
        pypath = make_dirs(root, "python")
        copy_module(import_name, pypath)

        if found_tools:
            binpath = make_dirs(root, "bin")
            for tool, src in sorted(found_tools.items()):
                dest = os.path.join(binpath, tool)
                shutil.copy2(src, dest)

        for name_ in extra_module_names:
            copy_module(name_, pypath)

    with make_package(name, path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.variants = [variant]

        if requires:
            pkg.requires = requires

        if found_tools:
            pkg.tools = list(found_tools)
            pkg.commands = commands_with_bin
        else:
            pkg.commands = commands

        for key, value in extra_attrs.items():
            pkg[key] = value

    return pkg.installed_variants
