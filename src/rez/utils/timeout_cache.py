from functools import update_wrapper
from threading import Thread, Lock
import time


def _make_key(nargs, kwargs):
    return (nargs, frozenset(kwargs.items()))


def timeout_cache(timeout=1, resolution=1):
    """Timeout cache decorator.

    Memoization decorator that evicts cached entries after a given time period.
    The entries are actively deleted - there is a dedicated thread that performs
    the deletes at the right time, meaning entries are evicted even if the
    wrapped function is never called again.

    Args:
        timeout (float): Time (in seconds) after which entries are deleted.
        resolution (float): How often the deleter thread performs evictions (in
            seconds)
    """
    def decorating_function(user_function):
        lock = Lock()
        entries = {}

        def deleter():
            keys = None
            while True:
                do_sleep = True

                # perform lots of small locks to avoid blocking writes
                if not keys:
                    with lock:
                        keys = entries.keys()

                for i, key in enumerate(keys):
                    with lock:
                        entry = entries.get(key)
                        if entry:
                            age = time.time() - entry[0]
                            if age > timeout:
                                del entries[key]
                                keys = keys[i:]
                                do_sleep = False
                                break

                if do_sleep:
                    time.sleep(resolution)

        th = Thread(target=deleter)
        th.setDaemon(True)
        th.start()

        def wrapper(*nargs, **kwargs):
            key = _make_key(nargs, kwargs)
            with lock:
                entry = entries.get(key)
                if entry is not None:
                    entry[0] = time.time()
                    return entry[1]

            value = user_function(*nargs, **kwargs)
            with lock:
                entries[key] = [time.time(), value]
            return value

        wrapper.__wrapped__ = user_function
        return update_wrapper(wrapper, user_function)

    return decorating_function
