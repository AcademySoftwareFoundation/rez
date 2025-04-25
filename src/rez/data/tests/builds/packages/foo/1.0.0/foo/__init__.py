import os

__version__ = os.getenv("REZ_FOO_VERSION")

def report() -> str:
    return "hello from foo-%s" % __version__
