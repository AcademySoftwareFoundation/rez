import errno
import os
import os.path
import re

from rez.utils.filesystem import find_matching_symlink


def get_next_base26(prev=None):
    """Increment letter-based IDs.

    Generates IDs like ['a', 'b', ..., 'z', 'aa', ab', ..., 'az', 'ba', ...]

    Returns:
        str: Next base-26 ID.
    """
    if not prev:
        return 'a'

    r = re.compile("^[a-z]*$")
    if not r.match(prev):
        raise ValueError("Invalid base26")

    if not prev.endswith('z'):
        return prev[:-1] + chr(ord(prev[-1]) + 1)

    return get_next_base26(prev[:-1]) + 'a'


def create_unique_base26_symlink(path, source):
    """Create a base-26 symlink in `path` pointing to `source`.

    If such a symlink already exists, it is returned. Note that there is a small
    chance that this function may create a new symlink when there is already one
    pointed at `source`.

    Assumes `path` only contains base26 symlinks.

    Returns:
        str: Path to created symlink.
    """
    retries = 0

    while True:
        # if a link already exists that points at `source`, return it
        name = find_matching_symlink(path, source)
        if name:
            return os.path.join(path, name)

        # get highest current symlink in path
        names = [
            x for x in os.listdir(path)
            if os.path.islink(os.path.join(path, x))
        ]

        if names:
            prev = max(names)
        else:
            prev = None

        linkname = get_next_base26(prev)
        linkpath = os.path.join(path, linkname)

        # attempt to create the symlink
        try:
            os.symlink(source, linkpath)
            return linkpath

        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # if we're here, the same named symlink was created in parallel
        # somewhere. Try again up to N times.
        #
        if retries > 10:
            raise RuntimeError(
                "Variant shortlink not created - there was too much contention.")
        retries += 1
