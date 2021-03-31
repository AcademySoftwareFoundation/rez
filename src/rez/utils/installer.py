from __future__ import print_function

import rez
from rez.package_maker import make_package
from rez.system import system
import os.path
import re
import sys
import shutil


def install_as_rez_package(repo_path):
    """Install the current rez installation as a rez package.

    Note: This is very similar to 'rez-bind rez', however rez-bind is intended
    for deprecation. Rez itself is a special case.

    Args:
        repo_path (str): Repository to install the rez package into.
    """
    def commands():
        env.PYTHONPATH.append('{this.root}')

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezplugins_path = os.path.join(site_path, "rezplugins")

        shutil.copytree(rez_path, os.path.join(root, "rez"))
        shutil.copytree(rezplugins_path, os.path.join(root, "rezplugins"))

    variant = system.variant
    variant.append("python-{0.major}.{0.minor}".format(sys.version_info))

    with make_package("rez", repo_path, make_root=make_root) as pkg:
        pkg.version = rez.__version__
        pkg.commands = commands
        pkg.variants = [variant]

    print('')
    print("Success! Rez was installed to %s/rez/%s" % (repo_path, rez.__version__))


def create_rez_production_scripts(target_dir, specifications):
    """Create Rez production scripts

    The script will be executed with Python interpreter flag -E, which will
    ignore all PYTHON* env vars, e.g. PYTHONPATH and PYTHONHOME.

    But for case like installing rez with `pip install rez --target <dst>`,
    which may install rez packages into a custom location that cannot be
    seen by Python unless setting PYTHONPATH, use REZ_PRODUCTION_PATH to
    expose <dst>, it will be appended into sys.path before execute.

    """
    import stat

    PYTHON_TEMPLATE = r'''# -*- coding: utf-8 -*-
import re
import os
import sys
if "REZ_PRODUCTION_PATH" in os.environ:
    sys.path.insert(0, os.environ["REZ_PRODUCTION_PATH"])
from %(module)s import %(import_name)s
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe\.cmd)?$', '', sys.argv[0])
    sys.exit(%(func)s())
'''

    CMD_TEMPLATE = r'''@echo off
set /p _rez_python=< %%~dp0.rez_production_install
%%_rez_python:~2%% -E %%~dp0%(name)s_.py %%*
'''

    BASH_TEMPLATE = r'''#!/bin/bash
export _rez_python=$(head -1 $(dirname $0)/.rez_production_install)
${_rez_python:2} -E $(dirname $0)/%(name)s_.py "$@"
'''

    scripts = []

    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    for specification in specifications:
        entry = _get_export_entry(specification)
        # add a trailing "_" to avoid module name conflict
        python_script = os.path.join(target_dir, entry.name) + "_.py"
        bash_script = os.path.join(target_dir, entry.name)
        cmd_script = os.path.join(target_dir, entry.name) + ".cmd"

        with open(python_script, "w") as s:
            s.write(PYTHON_TEMPLATE % dict(
                module=entry.prefix,
                import_name=entry.suffix.split('.')[0],
                func=entry.suffix
            ))

        with open(cmd_script, "w") as s:
            s.write(CMD_TEMPLATE % dict(name=entry.name))

        with open(bash_script, "w") as s:
            s.write(BASH_TEMPLATE % dict(name=entry.name))
        os.chmod(bash_script, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                 | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        scripts += [python_script, bash_script, cmd_script]

    return scripts


class _ExportEntry(object):
    """vended from distlib.scripts
    """
    def __init__(self, name, prefix, suffix, flags):
        self.name = name
        self.prefix = prefix
        self.suffix = suffix
        self.flags = flags


def _get_export_entry(specification):
    """vended from distlib.scripts
    """
    ENTRY_RE = re.compile(
        r'''(?P<name>(\w|[-.+])+)
        \s*=\s*(?P<callable>(\w+)([:\.]\w+)*)
        \s*(\[\s*(?P<flags>[\w-]+(=\w+)?(,\s*\w+(=\w+)?)*)\s*\])?
        ''', re.VERBOSE)

    m = ENTRY_RE.search(specification)
    if not m:
        result = None
        if '[' in specification or ']' in specification:
            raise Exception("Invalid specification '%s'" % specification)
    else:
        d = m.groupdict()
        name = d['name']
        path = d['callable']
        colons = path.count(':')
        if colons == 0:
            prefix, suffix = path, None
        else:
            if colons != 1:
                raise Exception("Invalid specification '%s'" % specification)
            prefix, suffix = path.split(':')
        flags = d['flags']
        if flags is None:
            if '[' in specification or ']' in specification:
                raise Exception("Invalid specification '%s'" % specification)
            flags = []
        else:
            flags = [f.strip() for f in flags.split(',')]
        result = _ExportEntry(name, prefix, suffix, flags)
    return result
