# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""Get full UNC path from a network drive letter if it exists
Adapted from: https://stackoverflow.com/a/34809340

Example:

    drive_mapping = get_connections()

    # Result:
    {
        'H:': u'\\\\server\\share\\username',
        'U:': u'\\\\server\\share\\simcache',
        'T:': u'\\\\server\\share',
        'C:': None,
        'Y:': u'\\\\server\\share\\reference',
        'Z:': u'\\\\server\\share\\production'
        'K:': u'\\\\server\\share2\\junk'
        'L:': u'\\\\server\\share\\library'
        'W:': u'\\\\server\\share\\mango'
    }

    unc = to_unc('H:')
    # Result: u'\\\\server\\share\\username'

    drive = to_drive('\\\\server\\share\\username')
    # Result: u'H:')

"""
import ctypes
from ctypes import wintypes
import os
import string

from rez.backport.lru_cache import lru_cache

mpr = ctypes.WinDLL('mpr')

ERROR_SUCCESS = 0x0000
ERROR_MORE_DATA = 0x00EA

wintypes.LPDWORD = ctypes.POINTER(wintypes.DWORD)
mpr.WNetGetConnectionW.restype = wintypes.DWORD
mpr.WNetGetConnectionW.argtypes = (
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPDWORD
)


@lru_cache()
def get_connections():
    """Get all available drive mappings

    Note: This function is cached, so it only runs once per session.

    Returns:
        dict: Drive mappings
    """
    available_drives = [
        '%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)
    ]
    return dict([d, _get_connection(d)] for d in available_drives)


def to_drive(unc):
    """Get drive letter from a UNC path

    Args:
        unc (str): UNC path

    Returns:
        str: Drive letter
    """
    connections = get_connections()
    drive = next(iter(k for k, v in connections.items() if v == unc), None)
    return drive


def to_unc(drive):
    """Get UNC path from a drive letter

    Args:
        drive (str): Drive letter

    Returns:
        str: UNC path
    """
    connections = get_connections()
    unc = connections.get(drive, None)
    return unc


def _get_connection(local_name, verbose=None):
    """Get full UNC path from a network drive letter if it exists

    Args:
        local_name (str): Drive letter name
        verbose (bool): Print errors

    Returns:
        str: Full UNC path to connection
    """
    length = (wintypes.DWORD * 1)()
    result = mpr.WNetGetConnectionW(local_name, None, length)
    if result != ERROR_MORE_DATA:
        if verbose:
            print(ctypes.WinError(result))
        return
    remote_name = (wintypes.WCHAR * length[0])()
    result = mpr.WNetGetConnectionW(local_name, remote_name, length)
    if result != ERROR_SUCCESS:
        if verbose:
            print(ctypes.WinError(result))
        return
    return remote_name.value
