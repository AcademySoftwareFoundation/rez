import sys
PY3 = sys.version_info > (3,)

if PY3:
    import rez.vendor.yaml.lib3
    sys.modules[__name__] = sys.modules["rez.vendor.yaml.lib3"]

else:
    import rez.vendor.yaml.lib
    sys.modules[__name__] = sys.modules["rez.vendor.yaml.lib"]
    
