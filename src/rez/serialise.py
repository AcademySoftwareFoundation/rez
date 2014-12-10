"""
Read and write data from file. File caching via a memcached server is supported.
"""
from rez.util import ScopeContext
from rez.exceptions import ResourceError
from rez.memcache import mem_cached, DataType
from rez.vendor.enum import Enum
from rez.vendor import yaml
import marshal
import os
import os.path


class FileFormat(Enum):
    py = ("py", DataType.code)
    yaml = ("yaml", DataType.data)
    txt = ("txt", DataType.data)

    __order__ = "py,yaml,txt"

    def __init__(self, extension, data_type):
        self.extension = extension
        self.data_type = data_type


"""
def listdir(path, use_cache=True):
    use_cache = use_cache and memcache_client.enabled
    filepath = os.path.realpath(filepath)

    if use_cache:
        st = os.stat(path)
        key = (path, st.st_ino, st.st_mtime)
        data = memcache_client.get(DataType.listdir, key)
        if data is not None:
            return data

    result = []
    for name in os.listdir(path):
        path_ = os.path.join(path, name)
        is_dir = os.path.isdir(path_)
        result.append((name, is_dir))

    if use_cache:
        memcache_client.set(DataType.listdir, key, result)

    return result
"""


def load_from_file(filepath, format_=FileFormat.py, update_data_callback=None):
    """Load data from a file.

    Args:
        filepath (str): File to load.
        format_ (`FileFormat`): Format of file contents.
        update_data_callback (callable): Used to change data before it is
            returned or cached.

    Returns:
        dict or compiled code object (if file is .py).
    """
    filepath = os.path.realpath(filepath)
    if format_ == FileFormat.py:
        return _load_from_py_file(filepath)
    else:
        return _load_from_file(filepath, format_, update_data_callback)


def _load_from_file__key(filepath, *nargs, **kwargs):
    st = os.stat(filepath)
    return (filepath, st.st_ino, st.st_mtime)


def _load_from_py_file__from_cache(marshalled_code, _):
    return marshal.loads(marshalled_code)


def _load_from_py_file__to_cache(code, _):
    return marshal.dumps(code)


def _load_from_py_file__value(code, filepath):
    return load_py(code, filepath)


@mem_cached(DataType.code,
            key_func=_load_from_file__key,
            from_cache_func=_load_from_py_file__from_cache,
            to_cache_func=_load_from_py_file__to_cache,
            value_func=_load_from_py_file__value)
def _load_from_py_file(filepath):
    with open(filepath) as f:
        source = f.read()
    code = compile(source, filepath, 'exec')
    return code


@mem_cached(DataType.data, key_func=_load_from_file__key)
def _load_from_file(filepath, format_, update_data_callback):
    load_func = load_yaml if format_ == FileFormat.yaml else load_txt
    with open(filepath) as f:
        result = load_func(f)

    if update_data_callback:
        result = update_data_callback(format_, result)
    return result


def load_py(stream, filepath=None):
    """Load python-formatted data from a stream or compiled code object.

    Note that the 'scoping' feature is supported and a `ScopeContext` named
    'scope' is made available (see scopes.py for more information). This
    means the python source can contain code like so:

        with scope("config") as c:
            release_packages_path = "/someserver/packages"
            c.plugins.release_hook.emailer.recipients = ['joe@bloggs.com']

    Args:
        stream (file-like object, or compiled code object).

    Returns:
        dict.
    """
    g = __builtins__.copy()
    scopes = ScopeContext()
    g['scope'] = scopes

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
    excludes = set(['scope', '__builtins__'])
    for k, v in g.iteritems():
        if k not in excludes and \
                (k not in __builtins__ or __builtins__[k] != v):
            result[k] = v

    result.update(scopes.to_dict())
    return result


def load_yaml(stream):
    """Load yaml-formatted data from a stream.

    Args:
        stream (file-like object).

    Returns:
        dict.
    """
    content = stream.read()
    return yaml.load(content) or {}


def load_txt(stream):
    """Load text data from a stream.

    Args:
        stream (file-like object).

    Returns:
        string.
    """
    content = stream.read()
    return content
