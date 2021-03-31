from __future__ import print_function

from rez.config import config
from rez.vendor.memcache.memcache import Client as Client_, \
    SERVER_MAX_KEY_LENGTH, __version__ as memcache_client_version
from rez.utils import py23
from threading import local
from contextlib import contextmanager
from functools import update_wrapper
from inspect import isgeneratorfunction
from hashlib import md5
from uuid import uuid4
from rez.vendor.six import six


basestring = six.string_types[0]


# this version should be changed if and when the caching interface changes
cache_interface_version = 2


class Client(object):
    """Wrapper for memcache.Client instance.

    Adds the features:
    - unlimited key length;
    - hard/soft flushing;
    - ability to cache None.
    """
    class _Miss(object):
        def __nonzero__(self):
            return False
        __bool__ = __nonzero__  # py3 compat

    miss = _Miss()

    logger = config.debug_printer("memcache")

    def __init__(self, servers, debug=False):
        """Create a memcached client.

        Args:
            servers (str or list of str): Server URI(s), eg '127.0.0.1:11211'.
            debug (bool): If True, quasi human readable keys are used. This helps
                debugging - run 'memcached -vv' in the foreground to see the keys
                being get/set/stored.
        """
        self.servers = [servers] if isinstance(servers, basestring) else servers
        self.key_hasher = self._debug_key_hash if debug else self._key_hash
        self._client = None
        self.debug = debug
        self.current = ''

    def __nonzero__(self):
        return bool(self.servers)

    __bool__ = __nonzero__  # py3 compat

    @property
    def client(self):
        """Get the native memcache client.

        Returns:
            `memcache.Client` instance.
        """
        if self._client is None:
            self._client = Client_(self.servers)
        return self._client

    def test_servers(self):
        """Test that memcached servers are servicing requests.

        Returns:
            set: URIs of servers that are responding.
        """
        responders = set()
        for server in self.servers:
            client = Client_([server])
            key = uuid4().hex
            client.set(key, 1)
            if client.get(key) == 1:
                responders.add(server)
        return responders

    def set(self, key, val, time=0, min_compress_len=0):
        """See memcache.Client."""
        if not self.servers:
            return

        key = self._qualified_key(key)
        hashed_key = self.key_hasher(key)
        val = (key, val)

        self.client.set(key=hashed_key,
                        val=val,
                        time=time,
                        min_compress_len=min_compress_len)
        self.logger("SET: %s", key)

    def get(self, key):
        """See memcache.Client.

        Returns:
            object: A value if cached, else `self.miss`. Note that this differs
            from `memcache.Client`, which returns None on cache miss, and thus
            cannot cache the value None itself.
        """
        if not self.servers:
            return self.miss

        key = self._qualified_key(key)
        hashed_key = self.key_hasher(key)
        entry = self.client.get(hashed_key)

        if isinstance(entry, tuple) and len(entry) == 2:
            key_, result = entry
            if key_ == key:
                self.logger("HIT: %s", key)
                return result

        self.logger("MISS: %s", key)
        return self.miss

    def delete(self, key):
        """See memcache.Client."""
        if self.servers:
            key = self._qualified_key(key)
            hashed_key = self.key_hasher(key)
            self.client.delete(hashed_key)

    def flush(self, hard=False):
        """Drop existing entries from the cache.

        Args:
            hard (bool): If True, all current entries are flushed from the
                server(s), which affects all users. If False, only the local
                process is affected.
        """
        if not self.servers:
            return
        if hard:
            self.client.flush_all()
            self.reset_stats()
        else:
            from uuid import uuid4
            tag = uuid4().hex
            if self.debug:
                tag = "flushed" + tag
            self.current = tag

    def get_stats(self):
        """Get server statistics.

        Returns:
            A list of tuples (server_identifier, stats_dictionary).
        """
        return self._get_stats()

    def reset_stats(self):
        """Reset the server stats."""
        self._get_stats("reset")

    def disconnect(self):
        """Disconnect from server(s). Behaviour is undefined after this call."""
        if self.servers and self._client:
            self._client.disconnect_all()
        # print("Disconnected memcached client %s" % str(self))

    def _qualified_key(self, key):
        """
        Qualify cache key so that:
        * changes to schemas don't break compatibility (cache_interface_version)
        * we're shielded from potential compatibility bugs in newer versions of
          python-memcached
        """
        return "%s:%s:%s:%s" % (
            memcache_client_version,
            cache_interface_version,
            self.current,
            key
        )

    def _get_stats(self, stat_args=None):
        return self.client.get_stats(stat_args=stat_args)

    @classmethod
    def _key_hash(cls, key):
        return md5(key.encode("utf-8")).hexdigest()

    @classmethod
    def _debug_key_hash(cls, key):
        import re
        h = cls._key_hash(key)[:16]
        value = "%s:%s" % (h, key)
        value = value[:SERVER_MAX_KEY_LENGTH]
        value = re.sub("[^0-9a-zA-Z]+", '_', value)
        return value


class _ScopedInstanceManager(local):
    def __init__(self):
        self.clients = {}

    def acquire(self, servers, debug=False):
        key = (tuple(servers or []), debug)
        entry = self.clients.get(key)
        if entry:
            entry[1] += 1
            return entry[0], key
        else:
            client = Client(servers, debug=debug)
            self.clients[key] = [client, 1]
            return client, key

    def release(self, key):
        entry = self.clients.get(key)
        assert entry

        entry[1] -= 1
        if not entry[1]:
            client = entry[0]
            del self.clients[key]
            client.disconnect()


scoped_instance_manager = _ScopedInstanceManager()


@contextmanager
def memcached_client(servers=config.memcached_uri, debug=config.debug_memcache):
    """Get a shared memcached instance.

    This function shares the same memcached instance across nested invocations.
    This is done so that memcached connections can be kept to a minimum, but at
    the same time unnecessary extra reconnections are avoided. Typically an
    initial scope (using 'with' construct) is made around parts of code that hit
    the cache server many times - such as a resolve, or executing a context. On
    exit of the topmost scope, the memcached client is disconnected.

    Returns:
        `Client`: Memcached instance.
    """
    key = None
    try:
        client, key = scoped_instance_manager.acquire(servers, debug=debug)
        yield client
    finally:
        if key:
            scoped_instance_manager.release(key)


def pool_memcached_connections(func):
    """Function decorator to pool memcached connections.

    Use this to wrap functions that might make multiple calls to memcached. This
    will cause a single memcached client to be shared for all connections.
    """
    if isgeneratorfunction(func):
        def wrapper(*nargs, **kwargs):
            with memcached_client():
                for result in func(*nargs, **kwargs):
                    yield result
    else:
        def wrapper(*nargs, **kwargs):
            with memcached_client():
                return func(*nargs, **kwargs)

    return update_wrapper(wrapper, func)


def memcached(servers, key=None, from_cache=None, to_cache=None, time=0,
              min_compress_len=0, debug=False):
    """memcached memoization function decorator.

    The wrapped function is expected to return a value that is stored to a
    memcached server, first translated by `to_cache` if provided. In the event
    of a cache hit, the data is translated by `from_cache` if provided, before
    being returned. If you do not want a result to be cached, wrap the return
    value of your function in a `DoNotCache` object.

    Example:

        @memcached('127.0.0.1:11211')
        def _listdir(path):
            return os.path.listdir(path)

    Note:
        If using the default key function, ensure that repr() is implemented on
        all your arguments and that they are hashable.

    Note:
        `from_cache` and `to_cache` both accept the value as first parameter,
        then the target function's arguments follow.

    Args:
        servers (str or list of str): memcached server uri(s), eg '127.0.0.1:11211'.
            This arg can be None also, in which case memcaching is disabled.
        key (callable, optional): Function that, given the target function's args,
            returns the string key to use in memcached.
        from_cache (callable, optional): If provided, and a cache hit occurs, the
            cached value will be translated by this function before being returned.
        to_cache (callable, optional): If provided, and a cache miss occurs, the
            function's return value will be translated by this function before
            being cached.
        time (int): Tells memcached the time which this value should expire, either
            as a delta number of seconds, or an absolute unix time-since-the-epoch
            value. See the memcached protocol docs section "Storage Commands"
            for more info on <exptime>. We default to 0 == cache forever.
        min_compress_len (int): The threshold length to kick in auto-compression
            of the value using the zlib.compress() routine. If the value being cached is
            a string, then the length of the string is measured, else if the value is an
            object, then the length of the pickle result is measured. If the resulting
            attempt at compression yeilds a larger string than the input, then it is
            discarded. For backwards compatability, this parameter defaults to 0,
            indicating don't ever try to compress.
        debug (bool): If True, memcache keys are kept human readable, so you can
            read them if running a foreground memcached proc with 'memcached -vv'.
            However this increases chances of key clashes so should not be left
            turned on.
    """
    def default_key(func, *nargs, **kwargs):
        parts = [func.__module__]
        argnames = py23.get_function_arg_names(func)

        if argnames:
            if argnames[0] == "cls":
                cls_ = nargs[0]
                parts.append(cls_.__name__)
                nargs = nargs[1:]
            elif argnames[0] == "self":
                cls_ = nargs[0].__class__
                parts.append(cls_.__name__)
                nargs = nargs[1:]

        parts.append(func.__name__)

        value = ('.'.join(parts), nargs, tuple(sorted(kwargs.items())))

        # make sure key is hashable. We don't strictly need it to be, but this
        # is a way of hopefully avoiding object types that are not ordered (these
        # would give an unreliable key). If you need to key on unhashable args,
        # you should provide your own `key` functor.
        #
        _ = hash(value)  # noqa

        return repr(value)

    def identity(value, *nargs, **kwargs):
        return value

    from_cache = from_cache or identity
    to_cache = to_cache or identity

    def decorator(func):
        if servers:
            def wrapper(*nargs, **kwargs):
                with memcached_client(servers, debug=debug) as client:
                    if key:
                        cache_key = key(*nargs, **kwargs)
                    else:
                        cache_key = default_key(func, *nargs, **kwargs)

                    # get
                    result = client.get(cache_key)
                    if result is not client.miss:
                        return from_cache(result, *nargs, **kwargs)

                    # cache miss - run target function
                    result = func(*nargs, **kwargs)
                    if isinstance(result, DoNotCache):
                        return result.result

                    # store
                    cache_result = to_cache(result, *nargs, **kwargs)
                    client.set(key=cache_key,
                               val=cache_result,
                               time=time,
                               min_compress_len=min_compress_len)
                    return result
        else:
            def wrapper(*nargs, **kwargs):
                result = func(*nargs, **kwargs)
                if isinstance(result, DoNotCache):
                    return result.result
                return result

        def forget():
            """Forget entries in the cache.

            Note that this does not delete entries from a memcached server - that
            would be slow and error-prone. Calling this function only ensures
            that entries set by the current process will no longer be seen during
            this process.
            """
            with memcached_client(servers, debug=debug) as client:
                client.flush()

        wrapper.forget = forget
        wrapper.__wrapped__ = func
        return update_wrapper(wrapper, func)
    return decorator


class DoNotCache(object):
    def __init__(self, result):
        self.result = result


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
