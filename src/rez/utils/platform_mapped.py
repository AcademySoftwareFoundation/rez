import re


def platform_mapped(func):
    """
    Decorates functions for lookups within a config.platform_map dictionary.
    The first level key is mapped to the func.__name__ of the decorated function.
    Regular expressions are used on the second level key, values.
    Note that there is no guaranteed order within the dictionary evaluation. Only the first matching
    regular expression is being used.
    For example:

    config.platform_map = {
        "os": {
            r"Scientific Linux-(.*)": r"Scientific-\1",    # Scientific Linux-x.x -> Scientific-x.x
            r"Ubuntu-14.\d": r"Ubuntu-14,                  # Any Ubuntu-14.x      -> Ubuntu-14
        },
        "arch": {
            "x86_64": "64bit",                             # Maps both x86_64 and amd64 -> 64bit
            "amd64": "64bit",
        },
    }
    """
    def inner(*args, **kwargs):

        # Since platform is being used within config lazy import config to prevent circular dependencies
        from rez.config import config

        # Original result
        result = func(*args, **kwargs)

        # The function name is used as primary key
        if func.__name__ in config.platform_map:
            for key, value in config.platform_map[func.__name__].iteritems():
                result, changes = re.subn(key, value, result)
                if changes > 0:
                    break
            return result

        return result
    return inner

