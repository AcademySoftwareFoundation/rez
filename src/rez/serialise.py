"""
Read and write data from file. File caching via a memcached server is supported.
"""
from contextlib import contextmanager
from inspect import isfunction, ismodule, getargspec
from StringIO import StringIO
import sys
import stat
import os
import os.path
import threading

from rez.package_resources_ import package_rex_keys
from rez.utils.scope import ScopeContext
from rez.utils.sourcecode import SourceCode, early, late, include
from rez.utils.filesystem import TempDirs
from rez.utils.data_utils import ModifyList
from rez.exceptions import ResourceError, InvalidPackageError
from rez.utils.memcached import memcached
from rez.utils.system import add_sys_paths
from rez.config import config
from rez.vendor.atomicwrites import atomic_write
from rez.vendor.enum import Enum
from rez.vendor import yaml


tmpdir_manager = TempDirs(config.tmpdir, prefix="rez_write_")
debug_print = config.debug_printer("file_loads")
file_cache = {}


class FileFormat(Enum):
    py = ("py",)
    yaml = ("yaml",)
    txt = ("txt",)

    __order__ = "py,yaml,txt"

    def __init__(self, extension):
        self.extension = extension


@contextmanager
def open_file_for_write(filepath, mode=None):
    """Writes both to given filepath, and tmpdir location.

    This is to get around the problem with some NFS's where immediately reading
    a file that has just been written is problematic. Instead, any files that we
    write, we also write to /tmp, and reads of these files are redirected there.

    Args:
        filepath (str): File to write.
        mode (int): Same mode arg as you would pass to `os.chmod`.

    Yields:
        File-like object.
    """
    stream = StringIO()
    yield stream
    content = stream.getvalue()

    filepath = os.path.realpath(filepath)
    tmpdir = tmpdir_manager.mkdtemp()
    cache_filepath = os.path.join(tmpdir, os.path.basename(filepath))

    debug_print("Writing to %s (local cache of %s)", cache_filepath, filepath)

    for attempt in range(2):
        try:
            with atomic_write(filepath, overwrite=True) as f:
                f.write(content)

        except WindowsError as e:
            if attempt == 0:
                # `overwrite=True` of atomic_write doesn't restore
                # writability to the file being written to.
                os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)

            else:
                # Under Windows, atomic_write doesn't tell you about
                # which file actually failed.
                raise WindowsError("%s: '%s'" % (e, filepath))

    if mode is not None:
        os.chmod(filepath, mode)

    with open(cache_filepath, 'w') as f:
        f.write(content)

    file_cache[filepath] = cache_filepath


def load_from_file(filepath, format_=FileFormat.py, update_data_callback=None,
                   disable_memcache=False):
    """Load data from a file.

    Note:
        Any functions from a .py file will be converted to `SourceCode` objects.

    Args:
        filepath (str): File to load.
        format_ (`FileFormat`): Format of file contents.
        update_data_callback (callable): Used to change data before it is
            returned or cached.
        disable_memcache (bool): If True, don't r/w to memcache.

    Returns:
        dict.
    """
    filepath = os.path.realpath(filepath)
    cache_filepath = file_cache.get(filepath)

    if cache_filepath:
        # file has been written by this process, read it from /tmp to avoid
        # potential write-then-read issues over NFS
        return _load_file(filepath=cache_filepath,
                          format_=format_,
                          update_data_callback=update_data_callback,
                          original_filepath=filepath)
    elif disable_memcache:
        return _load_file(filepath=filepath,
                          format_=format_,
                          update_data_callback=update_data_callback)
    else:
        return _load_from_file(filepath=filepath,
                               format_=format_,
                               update_data_callback=update_data_callback)


def _load_from_file__key(filepath, format_, update_data_callback):
    st = os.stat(filepath)
    if update_data_callback is None:
        callback_key = 'None'
    else:
        callback_key = getattr(update_data_callback, "__name__", "None")

    return str(("package_file", filepath, str(format_), callback_key,
                st.st_ino, st.st_mtime))


@memcached(servers=config.memcached_uri if config.cache_package_files else None,
           min_compress_len=config.memcached_package_file_min_compress_len,
           key=_load_from_file__key,
           debug=config.debug_memcache)
def _load_from_file(filepath, format_, update_data_callback):
    return _load_file(filepath, format_, update_data_callback)


def _load_file(filepath, format_, update_data_callback, original_filepath=None):
    load_func = load_functions[format_]

    if debug_print:
        if original_filepath:
            debug_print("Loading file: %s (local cache of %s)",
                        filepath, original_filepath)
        else:
            debug_print("Loading file: %s", filepath)

    with open(filepath) as f:
        result = load_func(f, filepath=filepath)

    if update_data_callback:
        result = update_data_callback(format_, result)
    return result


_set_objects = threading.local()


# Default variables to avoid not-defined errors in early-bound attribs
default_objects = {
    "building": False,
    "build_variant_index": 0,
    "build_variant_requires": []
}


def get_objects():
    """Get currently bound variables for evaluation of early-bound attribs.

    Returns:
        dict.
    """
    result = default_objects.copy()
    result.update(getattr(_set_objects, "variables", {}))
    return result


@contextmanager
def set_objects(objects):
    """Set the objects made visible to early-bound attributes.

    For example, `objects` might be used to set a 'build_variant_index' var, so
    that an early-bound 'private_build_requires' can change depending on the
    currently-building variant.

    Args:
        objects (dict): Variables to set.
    """
    _set_objects.variables = objects
    try:
        yield
    finally:
        _set_objects.variables = {}


def load_py(stream, filepath=None):
    """Load python-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    with add_sys_paths(config.package_definition_build_python_paths):
        return _load_py(stream, filepath=filepath)


def _load_py(stream, filepath=None):
    scopes = ScopeContext()

    g = dict(scope=scopes,
             early=early,
             late=late,
             include=include,
             ModifyList=ModifyList,
             InvalidPackageError=InvalidPackageError)

    try:
        exec stream in g
    except Exception as e:
        import traceback
        frames = traceback.extract_tb(sys.exc_info()[2])
        while filepath and frames and frames[0][0] != filepath:
            frames = frames[1:]

        msg = "Problem loading %s: %s" % (filepath, str(e))
        stack = ''.join(traceback.format_list(frames)).strip()
        if stack:
            msg += ":\n" + stack
        raise ResourceError(msg)

    result = {}
    excludes = set(('scope', 'InvalidPackageError', '__builtins__',
                    'early', 'late', 'include', 'ModifyList'))

    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v

    result.update(scopes.to_dict())
    result = process_python_objects(result, filepath=filepath)
    return result


class EarlyThis(object):
    """The 'this' object for @early bound functions.

    Just exposes raw package data as object attributes.
    """
    def __init__(self, data):
        self._data = data

    def __getattr__(self, attr):
        missing = object()
        value = self._data.get(attr, missing)
        if value is missing:
            raise AttributeError("No such package attribute '%s'" % attr)

        if isfunction(value) and (hasattr(value, "_early") or hasattr(value, "_late")):
            raise ValueError(
                "An early binding function cannot refer to another early or "
                "late binding function: '%s'" % attr)

        return value


def process_python_objects(data, filepath=None):
    """Replace certain values in the given package data dict.

    Does things like:
    * evaluates @early decorated functions, and replaces with return value;
    * converts functions into `SourceCode` instances so they can be serialized
      out to installed packages, and evaluated later;
    * strips some values (modules, __-leading variables) that are never to be
      part of installed packages.

    Returns:
        dict: Updated dict.
    """
    def _process(value):
        if isinstance(value, dict):
            for k, v in value.items():
                value[k] = _process(v)

            return value
        elif isfunction(value):
            func = value

            if hasattr(func, "_early"):
                # run the function now, and replace with return value
                #

                # make a copy of the func with its own globals, and add 'this'
                import types
                fn = types.FunctionType(func.func_code,
                                        func.func_globals.copy(),
                                        name=func.func_name,
                                        argdefs=func.func_defaults,
                                        closure=func.func_closure)

                # apply globals
                fn.func_globals["this"] = EarlyThis(data)
                fn.func_globals.update(get_objects())

                # execute the function
                spec = getargspec(func)
                args = spec.args or []
                if len(args) not in (0, 1):
                    raise ResourceError("@early decorated function must "
                                        "take zero or one args only")
                if args:
                    # this 'data' arg support isn't needed anymore, but I'm
                    # supporting it til I know nobody is using it...
                    #
                    value_ = fn(data)
                else:
                    value_ = fn()

                # process again in case this is a function returning a function
                return _process(value_)

            elif hasattr(func, "_late"):
                return SourceCode(func=func, filepath=filepath,
                                  eval_as_function=True)

            elif func.__name__ in package_rex_keys:
                # if a rex function, the code has to be eval'd NOT as a function,
                # otherwise the globals dict doesn't get updated with any vars
                # defined in the code, and that means rex code like this:
                #
                # rr = 'test'
                # env.RR = '{rr}'
                #
                # ..won't work. It was never intentional that the above work, but
                # it does, so now we have to keep it so.
                #
                return SourceCode(func=func, filepath=filepath,
                                  eval_as_function=False)

            else:
                # a normal function. Leave unchanged, it will be stripped after
                return func
        else:
            return value

    def _trim(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if isfunction(v):
                    if v.__name__ == "preprocess":
                        # preprocess is a special case. It has to stay intact
                        # until the `DeveloperPackage` has a chance to apply it;
                        # after which it gets removed from the package attributes.
                        #
                        pass
                    else:
                        del value[k]
                elif ismodule(v) or k.startswith("__"):
                    del value[k]
                else:
                    value[k] = _trim(v)

        return value

    data = _process(data)
    data = _trim(data)
    return data


def load_yaml(stream, **kwargs):
    """Load yaml-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    # if there's an error parsing the yaml, and you pass yaml.load a string,
    # it will print lines of context, but will print "<string>" instead of a
    # filename; if you pass a stream, it will print the filename, but no lines
    # of context.
    # Get the best of both worlds, by passing it a string, then replacing
    # "<string>" with the filename if there's an error...
    content = stream.read()
    try:
        return yaml.load(content) or {}
    except Exception, e:
        if stream.name and stream.name != '<string>':
            for mark_name in 'context_mark', 'problem_mark':
                mark = getattr(e, mark_name, None)
                if mark is None:
                    continue
                if getattr(mark, 'name') == '<string>':
                    mark.name = stream.name
        raise e


def load_txt(stream, **kwargs):
    """Load text data from a stream.

    Args:
        stream (file-like object).

    Returns:
        string.
    """
    content = stream.read()
    return content


def clear_file_caches():
    """Clear any cached files."""
    _load_from_file.forget()


load_functions = {FileFormat.py:      load_py,
                  FileFormat.yaml:    load_yaml,
                  FileFormat.txt:     load_txt}


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
