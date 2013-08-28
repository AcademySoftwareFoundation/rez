import memcache
import hashlib
import pickle
import sys
import copy


class MemCacheClient(object):
    """
    Wrapper for memcache.Client class.
    """
    def __init__(self, client, verbose=True):
        self.mc = client
        self.verbose = verbose

    def _get_key(self, k):
        if isinstance(k, basestring) and len(k) < self.mc.server_max_key_length:
            return k.replace(' ','_')
        else:
            return hashlib.sha512(pickle.dumps(k)).hexdigest()

    def _set(self, k, v, fn):
        return fn(self._get_key(k), v, min_compress_len=self.mc.server_max_value_length/2)        

    def set(self, k, v):
        return self._set(k, v, self.mc.set)

    def cas(self, k, v):
        return self._set(k, v, self.mc.cas)

    def add(self, k, v):
        return self._set(k, v, self.mc.add)

    def get(self, k):
        return self.mc.get(self._get_key(k))

    def gets(self, k):
        return self.mc.gets(self._get_key(k))

    def update(self, k, fn, initial):
        """
        Atomic update function.
        """
        assert(initial is not None)
        while True:
            v = self.gets(k)
            if v is None:
                v = fn(copy.deepcopy(initial))
                if self.add(k, v):
                    return
            elif self.cas(k, fn(v)):
                return

    # convenience update functions
    @staticmethod
    def _add_to_set(v, item):
        v.add(item)
        return v

    def update_add_to_set(self, k, item):
        fn = lambda v: MemCacheClient._add_to_set(v, item)
        self.update(k, fn, set())
