"""
Read and write data from a file or stream. File caching via a memcached server
is supported.
"""
from rez.util import ScopeContext
from rez.exceptions import ResourceError
from rez.memcache import memcache_client, DataType
from rez.vendor.enum import Enum
from rez.vendor import yaml
import marshal
import os


class FileFormat(Enum):
    py = ("py", DataType.code)
    yaml = ("yaml", DataType.data)

    __order__ = "py,yaml"  # py is preferred

    def __init__(self, extension, data_type):
        self.extension = extension
        self.data_type = data_type


def load_from_file(filepath, format_=FileFormat.py, use_cache=True):
    """Load data from a file.

    Args:
        filepath (str): File to load.
        format_ (`FileFormat`): Format of file contents.
        use_cache (bool): If True, use memcached server if available.

    Returns:
        dict.
    """
    use_cache = use_cache and memcache_client.enabled

    if use_cache:
        st = os.stat(filepath)
        key = (filepath, st.st_ino, st.st_mtime)
        data = memcache_client.get(format_.data_type, key)

        if data is not None:
            if format_.data_type == DataType.data:
                return data
            else:  # DataType.data
                code = marshal.loads(data)
                return load_py(code, filepath)

    if format_ == FileFormat.py:
        with open(filepath) as f:
            source = f.read()
        code = compile(source, filepath, 'exec')
        result = load_py(code, filepath)
        if use_cache:
            data = marshal.dumps(code)
    else:
        with open(filepath) as f:
            result = data = load_yaml(f, filepath)

    if use_cache:
        memcache_client.set(format_.data_type, key, data)

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


def load_yaml(stream, filepath=None):
    """Load yaml-formatted data from a stream.

    Args:
        stream (file-like object).
    """
    content = stream.read()
    return yaml.load(content) or {}
