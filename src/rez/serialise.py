"""
Read and write data from file. File caching via a memcached server is supported.
"""
from rez.utils.scope import ScopeContext
from rez.utils.data_utils import SourceCode
from rez.utils.logging_ import print_debug
from rez.utils.filesystem import TempDirs
from rez.exceptions import ResourceError
from rez.utils.memcached import memcached
from rez.config import config
from rez.vendor.enum import Enum
from rez.vendor import yaml
from contextlib import contextmanager
from inspect import isfunction
from StringIO import StringIO
import sys
import os
import os.path


tmpdir_manager = TempDirs(config.tmpdir, prefix="rez_write_")


file_cache = {}


class FileFormat(Enum):
    py = ("py",)
    yaml = ("yaml",)
    txt = ("txt",)

    __order__ = "py,yaml,txt"

    def __init__(self, extension):
        self.extension = extension


@contextmanager
def open_file_for_write(filepath):
    """Writes both to given filepath, and tmpdir location.

    This is to get around the problem with some NFS's where immediately reading
    a file that has just been written is problematic. Instead, any files that we
    write, we also write to /tmp, and reads of these files are redirected there.
    """
    stream = StringIO()
    yield stream
    content = stream.getvalue()

    filepath = os.path.realpath(filepath)
    tmpdir = tmpdir_manager.mkdtemp()
    cache_filepath = os.path.join(tmpdir, os.path.basename(filepath))

    with open(filepath, 'w') as f:
        f.write(content)

    with open(cache_filepath, 'w') as f:
        f.write(content)

    file_cache[filepath] = cache_filepath


def load_from_file(filepath, format_=FileFormat.py, update_data_callback=None):
    """Load data from a file.

    Note:
        Any functions from a .py file will be converted to `SourceCode` objects.

    Args:
        filepath (str): File to load.
        format_ (`FileFormat`): Format of file contents.
        update_data_callback (callable): Used to change data before it is
            returned or cached.

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
                          update_data_callback=update_data_callback)
    else:
        return _load_from_file(filepath=filepath,
                               format_=format_,
                               update_data_callback=update_data_callback)


def _load_from_file__key(filepath, *nargs, **kwargs):
    st = os.stat(filepath)
    return str(("package_file", filepath, st.st_ino, st.st_mtime))


@memcached(servers=config.memcached_uri if config.cache_package_files else None,
           min_compress_len=config.memcached_package_file_min_compress_len,
           key=_load_from_file__key,
           debug=config.debug_memcache)
def _load_from_file(filepath, format_, update_data_callback):
    return _load_file(filepath, format_, update_data_callback)


def _load_file(filepath, format_, update_data_callback):
    load_func = load_functions[format_]

    if config.debug("file_loads"):
        print_debug("Loading file: %s" % filepath)

    with open(filepath) as f:
        result = load_func(f, filepath=filepath)

    if update_data_callback:
        result = update_data_callback(format_, result)
    return result


def load_py(stream, filepath=None):
    """Load python-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    scopes = ScopeContext()
    g = dict(scope=scopes)

    try:
        exec stream in g
    except Exception as e:
        import traceback
        frames = traceback.extract_tb(sys.exc_info()[2])
        while filepath and frames and frames[0][0] != filepath:
            frames = frames[1:]

        msg = str(e)
        stack = ''.join(traceback.format_list(frames)).strip()
        if stack:
            msg += ":\n" + stack
        raise ResourceError(msg)

    result = {}
    excludes = set(('scope', '__builtins__'))
    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v

    def _process_objects(data):
        for k, v in data.iteritems():
            if isfunction(v):
                data[k] = SourceCode.from_function(v)
            elif isinstance(v, dict):
                _process_objects(v)
        return data

    result.update(scopes.to_dict())
    result = _process_objects(result)
    return result


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
