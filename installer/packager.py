# Adapted from Ronny Pfannschmidt's genscript package
# https://bitbucket.org/RonnyPfannschmidt/genscript

import sys
import pickle
import base64
import os
from fnmatch import fnmatch


def find_toplevel(name):
    for syspath in sys.path:
        lib = os.path.join(syspath, name)
        if os.path.isdir(lib):
            return lib
        mod = lib + '.py'
        if os.path.isfile(mod):
            return mod
    raise LookupError(name)


def path_to_source(name, ignore=None, patterns=None):
    toplevel = find_toplevel(name)
    if os.path.isfile(toplevel):
        return {name: toplevel.read()}

    def _relpath(path):
        relpath = os.path.normpath(os.path.relpath(path, toplevel))
        return os.path.join(name, relpath)

    def _ignore(path):
        if ignore:
            rpath = _relpath(path)
            return (rpath in ignore)
        else:
            return False

    path2src = {}
    patterns = patterns or ("*.py",)

    for root, dirs, files in os.walk(toplevel):
        if not _ignore(root):
            for file in files:
                match = False
                for pattern in patterns:
                    if fnmatch(file, pattern):
                        match = True
                        break
                if match:
                    filepath = os.path.join(root, file)
                    if not _ignore(filepath):
                        relpath = _relpath(filepath)
                        f = open(os.path.join(root, file))
                        try:
                            path2src[relpath] = f.read()
                        finally:
                            f.close()
    return path2src


def encode_mapping(mapping):
    data = pickle.dumps(mapping, pickle.HIGHEST_PROTOCOL)
    data = base64.encodestring(data)
    return data


def encode_packages(names, ignores=None, patterns=None):
    mapping = {}
    for name in names:
        ignore = (ignores or {}).get(name)
        mapping.update(path_to_source(name, ignore, patterns))
    return encode_mapping(mapping)


def _entab(text, spaces=4):
    return '\n'.join([(' ' * 4) + t for t in text.split('\n')])


def generate_script(entry, packages, ignores=None, patterns=None):
    data = encode_packages(packages, ignores, patterns)
    tmpl = open(os.path.join(os.path.dirname(__file__), 'template.py'))
    exe = tmpl.read()
    tmpl.close()
    exe = exe.replace('@SOURCES@', data)
    exe = exe.replace('    #@ENTRY@', _entab(entry))
    return exe
