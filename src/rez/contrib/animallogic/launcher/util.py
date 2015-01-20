import string


class DefaultFormatter(string.Formatter):
    def __init__(self, default=' '):
        self.default = default

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, self.default)
        else:
            Formatter.get_value(key, args, kwargs)


def truncate_timestamp(timestamp):
    """
    The timestamps returned by launcher are 3 digits longer than those used by
    python.  This utility function can be used to trim off the extra digits to
    ensure the Launcher preset timestamp can be used in the Python code.
    """
    return int(str(timestamp)[:-3])
