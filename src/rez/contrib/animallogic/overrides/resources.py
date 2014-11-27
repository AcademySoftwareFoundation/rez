from functools import wraps
from rez.vendor.version.version import Version

def check_node(wrapped):
    """
    The package.yaml files used with Rez 1.7 have the version number specified 
    as a float, int or string.  However the current implementation of 
    rez.resources.MetadataValidator.check_node expects a string only.  Here we 
    intercept the incorrect node and coerce it into the correct type.
    """

    @wraps(wrapped)
    def wrapper(self, node, refnode, id=''):

        if type(node) != type(refnode):
            if node is not None:
                if type(refnode).__module__ != '__builtin__':
                    if isinstance(refnode, (Version,)) and isinstance(node, (float, int)):
                        node = str(node)

        return wrapped(self, node, refnode, id=id)

    return wrapper

