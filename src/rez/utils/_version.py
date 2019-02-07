

# Update this value to version up Rez. Do not place anything else in this file.
_rez_version = "2.27.0"

try:
    from rez.vendor.version.version import Version
    _rez_Version = Version(_rez_version)
except:
    # the installer imports this file...
    pass


