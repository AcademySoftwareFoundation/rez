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
    data = (1, False)   # a dict of POD types
    code = (2, True)    # source from py file

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
