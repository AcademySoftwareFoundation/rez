from rez.config import config
from rez.vendor.memcached import memcache
from rez.util import print_debug


_g_client = None


def connect():
    global _g_client

    if config.memcache_enabled and _g_client is None:
        if config.debug("memcache"):
            print_debug("connecting to memcache servers %s." % config.memcache_servers)

        _g_client = memcache.Client(config.memcache_servers,
                                    debug=int(config.memcache_client_debug))

    return _g_client


def disconnect():
    global _g_client

    if _g_client:
        if config.debug("memcache"):
            print_debug("disconnecting all memcache servers.")

        connect().disconnect_all()
        _g_client = None


def get(key):

    connection = connect()
    if connection:
        if config.debug("memcache"):
            print_debug("fetching key '%s' from memcache." % key)

        return connection.get(key)

    return None


def set(key, value):

    connection = connect()

    if connection:
        if config.debug("memcache"):
            print_debug("setting key '%s' in memcache." % key)

        return connection.set(key, value, time=config.memcache_ttl)

    return False
