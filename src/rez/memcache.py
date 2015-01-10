"""
Memcached client wrapper.
"""
from rez import __version__
from rez.config import config
from rez.utils.data_utils import cached_property
from rez.vendor.enum import Enum
from rez.vendor.memcache.memcache import Client as Client_, SERVER_MAX_KEY_LENGTH
from hashlib import md5


class DataType(Enum):
    package_file = (1, config.memcached_package_file_min_compress_len)  # data from a package file
    listdir = (2, config.memcached_listdir_min_compress_len)            # cached os.listdir result
    resolve = (3, config.memcached_resolve_min_compress_len)            # a package request solve

    def __init__(self, id_, min_compress_len):
        self.id_ = id_
        self.min_compress_len = min_compress_len


class Client(object):
    def __init__(self):
        self.key_offset = __version__
        if config.debug_memcache:
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

    def flush(self, hard=False):
        """Drop existing entries from the cache.

        Args:
            hard (bool): If True, all current entries are flushed from the
                server(s), which affects all users. If False, only the local
                process is affected.
        """
        if hard:
            # flushes server(s), reset stats
            self.client.flush_all()
            self.reset_stats()
        else:
            # set our counter to some unique value. This offsets our keys so
            # that they don't match anyone else's
            from uuid import uuid4
            self.key_offset = "%s:%s" % (__version__, uuid4().hex)

    def get_stats(self):
        """Get server statistics.

        Returns:
            A list of tuples (server_identifier, stats_dictionary).
        """
        return self._get_stats()

    def reset_stats(self):
        """Reset the server stats."""
        self._get_stats("reset")

    @cached_property
    def client(self):
        uris = config.memcached_uri
        if uris:
            mc = Client_(uris)
            mc.set("__test__", 1)
            if mc.get("__test__") == 1:
                return mc
            else:
                from rez.utils.colorize import Printer, error
                import sys
                msg = "Failed to connect to memcached: %s" % ", ".join(uris)
                Printer(sys.stderr)(msg, error)
        return None

    def get_summary_string(self):
        from rez.utils.formatting import columnise, readable_time_duration, \
            readable_memory_size

        stats = self.get_stats()
        if not stats:
            return None

        rows = [["CACHE SERVER", "UPTIME", "HITS", "MISSES", "HIT RATIO", "MEMORY", "USED"],
                ["------------", "------", "----", "------", "---------", "------", "----"]]

        for server_id, stats_dict in stats:
            server_uri = server_id.split()[0]
            uptime = int(stats_dict.get("uptime", 0))
            hits = int(stats_dict.get("get_hits", 0))
            misses = int(stats_dict.get("get_misses", 0))
            memory = int(stats_dict.get("limit_maxbytes", 0))
            used = int(stats_dict.get("bytes", 0))

            hit_ratio = float(hits) / max(hits + misses, 1)
            hit_percent = int(hit_ratio * 100.0)
            used_ratio = float(used) / max(memory, 1)
            used_percent = int(used_ratio * 100.0)

            row = (server_uri,
                   readable_time_duration(uptime),
                   str(hits),
                   str(misses),
                   "%d%%" % hit_percent,
                   readable_memory_size(memory),
                   "%s (%d%%)" % (readable_memory_size(used), used_percent))

            rows.append(row)
        return '\n'.join(columnise(rows))

    def _key_hash(self, type_, key):
        t = (self.key_offset, type_.id_, key)
        return md5(str(t)).hexdigest()

    def _key_hash_debug(self, type_, key):
        h = self._key_hash(type_, key)[:16]
        str_key = str(key).replace(' ', '_')
        value = "%s:%s:%s" % (h, type_.name, str_key)
        return value[:SERVER_MAX_KEY_LENGTH]

    def _get_stats(self, stat_args=None):
        return self.client.get_stats(stat_args=stat_args)


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
            translated by this function before being returned, regardless of
            whether a cache hit or miss occurred.

    Note:
        `from_cache_func`, `to_cache_func` and `value_func` all accept a return
        value as first parameter, then the target function's arguments follow.
        Both are expected to return the translated result.

    Note:
        You can override `data_type` by passing the kwarg '_data_type' to the
        decorated function. This argument is not passed to the wrapped function.
    """
    def decorator(func):
        def wrapper(*nargs, **kwargs):
            data_type_ = kwargs.pop("_data_type", data_type)

            if memcache_client.enabled:
                if key_func is None:
                    key = (nargs, frozenset(kwargs.items()))
                else:
                    key = key_func(*nargs, **kwargs)

                data = memcache_client.get(data_type_, key)
                if data is None:
                    def _set(value):
                        value_ = _None() if value is None else value
                        memcache_client.set(data_type_, key, value_)

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
