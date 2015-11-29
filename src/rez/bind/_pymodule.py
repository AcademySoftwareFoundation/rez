"""
Binds a python module to rez.
"""
from __future__ import absolute_import
from rez.bind._utils import check_version, find_exe, make_dirs
from rez.package_maker__ import make_package
from rez.backport.importlib import import_module
from rez.exceptions import RezBindError
from rez.system import system
import shutil
import sys
import os.path


def commands():
    env.PYTHONPATH.append('{this.root}/python')


def commands_with_bin():
    env.PYTHONPATH.append('{this.root}/python')
    env.PATH.append('{this.root}/bin')


def copy_module(name, destpath):
    try:
        module = import_module(name)
    except ImportError:
        raise RezBindError("Could not find python module '%s' on the system" % name)

    if hasattr(module, "__path__"):
        srcpath = module.__path__[0]
        shutil.copytree(srcpath, os.path.join(destpath, name))
    else:
        srcfile = module.__file__
        dirpart, ext = os.path.splitext(srcfile)

        if ext == ".pyc":
            pyfile = dirpart + ".py"
            if os.path.exists(pyfile):
                srcfile = pyfile

        destfile = os.path.join(destpath, os.path.basename(srcfile))
        shutil.copy2(srcfile, destfile)


def bind(name, path, version_range=None, pure_python=None, tools=None,
         extra_module_names=[], extra_attrs={}):
    module = import_module(name)

    version = module.__version__
    check_version(version, version_range)

    py_major_minor = '.'.join(str(x) for x in sys.version_info[:2])
    py_req = "python-%s" % py_major_minor

    if pure_python is None:
        raise NotImplementedError  # detect
    elif pure_python:
        variant = [py_req]
    else:
        variant = system.variant + [py_req]

    def make_root(variant, root):
        pypath = make_dirs(root, "python")
        copy_module(name, pypath)

        for name_ in extra_module_names:
            copy_module(name_, pypath)

        if tools:
            binpath = make_dirs(root, "bin")
            for tool in tools:
                src = find_exe(tool)
                dest = os.path.join(binpath, tool)
                shutil.copy2(src, dest)

    with make_package(name, path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.variants = [variant]

        if tools:
            pkg.tools = list(tools)
            pkg.commands = commands_with_bin
        else:
            pkg.commands = commands

        for key, value in extra_attrs.iteritems():
            pkg[key] = value

    return version
