"""
Read and write data from file. File caching via a memcached server is supported.
"""
from rez.utils.scope import ScopeContext, RecursiveAttribute
from rez.utils.data_utils import SourceCode
from rez.exceptions import ResourceError
from rez.memcache import mem_cached, DataType
from rez.vendor.enum import Enum
from rez.vendor import yaml
from inspect import isfunction
import os
import os.path


class FileFormat(Enum):
    py = ("py", DataType.data)
    yaml = ("yaml", DataType.data)
    txt = ("txt", DataType.data)

    __order__ = "py,yaml,txt"

    def __init__(self, extension, data_type):
        self.extension = extension
        self.data_type = data_type


def load_from_file(filepath, format_=FileFormat.py, recursive_attributes=None,
                   update_data_callback=None):
    """Load data from a file.

    Note:
        Any function from a .py file will be converted to a `SourceCode` instance.

    Args:
        filepath (str): File to load.
        format_ (`FileFormat`): Format of file contents.
        recursive_attributes (list of str): Only used in python files. If any
            names are provided, empty `RecursiveAttribute` instances are created.
        update_data_callback (callable): Used to change data before it is
            returned or cached.

    Returns:
        dict.
    """
    filepath = os.path.realpath(filepath)
    return _load_from_file(filepath, format_, recursive_attributes,
                           update_data_callback)


def _load_from_file__key(filepath, *nargs, **kwargs):
    st = os.stat(filepath)
    return (filepath, st.st_ino, st.st_mtime)


@mem_cached(DataType.data, key_func=_load_from_file__key)
def _load_from_file(filepath, format_, recursive_attributes, update_data_callback):
    load_func = load_functions[format_]
    with open(filepath) as f:
        result = load_func(f, filepath=filepath,
                           recursive_attributes=recursive_attributes)

    if update_data_callback:
        result = update_data_callback(format_, result)
    return result


def load_py(stream, filepath=None, recursive_attributes=None):
    """Load python-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    g = __builtins__.copy()
    scopes = ScopeContext()
    g['scope'] = scopes

    attrs = {}
    for name in (recursive_attributes or []):
        attr = RecursiveAttribute()
        attrs[name] = attr
        g[name] = attr

    try:
        exec stream in g
    except Exception as e:
        import traceback
        frames = traceback.extract_tb(sys.exc_info()[2])
        while filepath and frames and frames[0][0] != filepath:
            frames = frames[1:]
        stack = ''.join(traceback.format_list(frames)).strip()
        raise ResourceError("%s:\n%s" % (str(e), stack))

    result = {}
    excludes = set(('scope', '__builtins__'))
    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            if isfunction(v):
                v = SourceCode.from_function(v)
            result[k] = v

    result.update(scopes.to_dict())
    for name, attr in attrs.iteritems():
        d = attr.to_dict()
        if d:
            result[name] = d

    return result


def load_yaml(stream, **kwargs):
    """Load yaml-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    content = stream.read()
    return yaml.load(content) or {}


def load_txt(stream, **kwargs):
    """Load text data from a stream.

    Args:
        stream (file-like object).

    Returns:
        string.
    """
    content = stream.read()
    return content


load_functions = {FileFormat.py:      load_py,
                  FileFormat.yaml:    load_yaml,
                  FileFormat.txt:     load_txt}
