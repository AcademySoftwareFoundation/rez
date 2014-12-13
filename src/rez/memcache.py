"""
Memcached client wrapper.
"""
from rez import __version__
from rez.config import config
from rez.utils.data_utils import cached_property
from rez.vendor.enum import Enum
from rez.vendor.memcache import memcache
from imp import get_magic
from hashlib import md5


magic = get_magic()


class DataType(Enum):
    data = (1, False, 0)        # a dict of POD types from a file (eg yaml)
    code = (2, True, 0)         # source from py file (marshalled)
    listdir = (3, False, 0)     # cached os.listdir result
    resolve = (4, False, 1)     # a package request solve

    def __init__(self, id_, bytecode_dependent, min_compress_len):
        self.id_ = id_
        self.bytecode_dependent = bytecode_dependent
        self.min_compress_len = min_compress_len


class Client(object):
    def __init__(self):
        self.counter = 0
        if config.debug_memcache_keys:
            self._key_hash_fn = self._key_hash_debug
        else:
            self._key_hash_fn = self._key_hash

    @property
    def enabled(self):
        return (self.client is not None)

    def set(self, type_, key, value):
        h = self._key_hash_fn(type_, key)
        data = (type_.id_, key, value)
        self.client.set(h, data, min_compress_len=type_.min_compress_len)

    def get(self, type_, key):
        h = self._key_hash_fn(type_, key)
        hit = self.client.get(h)
        if hit is not None:
            _type_id, _key, value = hit
            if _type_id == type_.id_ and _key == key:  # avoid hash collisions
                return value
        return None

    def delete(self, type_, key):
        h = self._key_hash_fn(type_, key)
        self.client.delete(h)

    def flush(self):
        """Drop existing entries from the cache.

        This does not actually flush the memcache, which is deliberate - other
        processes using rez will be unaffected.
        """
        self.counter += 1

    @cached_property
    def client(self):
        uris = config.memcached_uri
        if uris:
            mc = memcache.Client(uris)
            mc.set("__test__", 1)
            if mc.get("__test__") == 1:
                return mc
        return None

    def _key_hash(self, type_, key):
        t = [self.counter, type_.id_, __version__]
        if type_.bytecode_dependent:
            t.append(magic)
        t.append(key)
        return md5(str(t)).hexdigest()

    def _key_hash_debug(self, type_, key):
        h = self._key_hash(type_, key)[:16]
        str_key = str(key).replace(' ', '_')
        value = "%s:%s:%s" % (h, type_.name, str_key)
        return value[:250]  # 250 is memcached's max key length


# singleton
memcache_client = Client()


class DoNotCache(object):
    def __init__(self, result):
        self.result = result


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

    If you do not want a result to be cached, wrap the return value of your
    function in a `DoNotCache` object. Note that `value_func` will still be
    applied in this case.

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
            if memcache_client.enabled:
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
                    if isinstance(result, DoNotCache):
                        result = result.result
                    elif to_cache_func is None:
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
            else:
                result = func(*nargs, **kwargs)
                if isinstance(result, DoNotCache):
                    result = result.result

            if value_func is not None:
                result = value_func(result, *nargs, **kwargs)

            return result
        return wrapper
    return decorator
