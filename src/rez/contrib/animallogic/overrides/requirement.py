from functools import wraps
from rez.util import encode_filesystem_name

def safe_str(wrapped):
    """
    """

    @wraps(wrapped)
    def wrapper(self):

        return encode_filesystem_name(str(self))

    return wrapper
