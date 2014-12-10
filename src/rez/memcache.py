"""
Memcached client wrapper.
"""
from rez import __version__
from rez.config import config
from rez.utils.data_utils import cached_property
from rez.vendor.enum import Enum
from rez.vendor.memcache import memcache
from imp import get_magic


magic = get_magic()


class DataType(Enum):
    data = (1, False)   # a dict of POD types from a file (eg yaml)
    code = (2, True)    # source from py file (marshalled)
    listdir = (3, False)  # cached os.listdir result

    def __init__(self, id_, bytecode_dependent):
        self.id_ = id_
        self.bytecode_dependent = bytecode_dependent


class Client(object):
    def __init__(self):
        pass

    @property
    def enabled(self):
        return (self.client is not None)

    def set(self, type_, key, value):
        h = self._key_hash(type_, key)
        self.client.set(h, (type_, key, value))

    def get(self, type_, key):
        h = self._key_hash(type_, key)
        hit = self.client.get(h)
        if hit is not None:
            _type, _key, value = hit
            if _type == type_ and _key == key:  # avoid hash collisions
                return value
        return None

    @cached_property
    def client(self):
        uris = config.memcached_uri
        if uris:
            uris_ = []
            for uri in uris:
                mc = memcache.Client([uri])
                mc.set("__test__", 1)
                if mc.get("__test__") == 1:
                    uris_.append(uri)
                mc = None

            if uris_:
                return memcache.Client(uris_)
        return None

    @classmethod
    def _key_hash(cls, type_, key):
        t = [type_.id_, __version__]
        if type_.bytecode_dependent:
            t.append(magic)
        t.append(key)
        return str(hash(tuple(t)))


# singleton
memcache_client = Client()


class _None(object):
    pass


def mem_cached(data_type, key_func=None, from_cache_func=None,
               to_cache_func=None, value_func=None):
    """memcached function decorator.

    The wrapped function is expected to return a value that is stored to a
    memcached server, first translated by `to_cache_func` if provided.

    In the event of a cache hit, the data is translated by `from_cache_func` if
    provided, before being returned.

    In all cases (cache hits and misses), the result is translated by `value_func`
    if provided, after from_cache_func/to_cache_func has been called.

    Note:
        This decorator will also cache a None result.

    Args:
        data_type (`DataType`): Type of data the function returns.
        key_func (callable, optional): Function that, given the target function's
            args, returns the key to use in memcached. If None, the args are used
            directly. Note that if any arg is not hashable, you will have to
            provide this key function.
        from_cache_func (callable, optional): If provided, and a cache hit occurs,
            the value will be translated by this function before being returned.
        to_cache_func (callable, optional): If provided, and a cache miss occurs,
            the value will be translated by this function before being cached.
        value_func (callable, optional): If provided, the result is first
            translated by this function before being returned.

    Note:
        `from_cache_func`, `to_cache_func` and `value_func` all accept a return
        value as first parameter, then the target function's arguments follow.
        Both are expected to return the translated result.
    """
    def decorator(func):
        def wrapper(*nargs, **kwargs):
            if not memcache_client.enabled:
                return func(*nargs, **kwargs)

            if key_func is None:
                key = (nargs, frozenset(kwargs.items()))
            else:
                key = key_func(*nargs, **kwargs)

            data = memcache_client.get(data_type, key)
            if data is None:
                def _set(value):
                    value_ = _None() if value is None else value
                    memcache_client.set(data_type, key, value_)

                result = func(*nargs, **kwargs)
                if to_cache_func is None:
                    _set(result)
                else:
                    data = to_cache_func(result, *nargs, **kwargs)
                    _set(data)
            else:
                if isinstance(data, _None):
                    data = None

                if from_cache_func is None:
                    result = data
                else:
                    result = from_cache_func(data, *nargs, **kwargs)

            if value_func is not None:
                result = value_func(result, *nargs, **kwargs)

            return result
        return wrapper
    return decorator
