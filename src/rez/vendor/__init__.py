import sys

if sys.version_info[0] == 2:
    from ._python2 import yaml
    from ._python2 import sortedcontainers
else:
    from ._python3 import yaml
    from ._python3 import sortedcontainers


sys.modules[__name__ + ".yaml"] = yaml
sys.modules[__name__ + ".sortedcontainers"] = sortedcontainers
