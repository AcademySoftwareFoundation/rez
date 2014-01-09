# Backport of Python-2.7.4 os.path._joinrealpath

# Join two paths, normalizing ang eliminating any symbolic links
# encountered in the second path.
def _joinrealpath(path, rest, seen):
    from os.path import isabs, sep, curdir, pardir, split, join, islink
    if isabs(rest):
        rest = rest[1:]
        path = sep

    while rest:
        name, _, rest = rest.partition(sep)
        if not name or name == curdir:
            # current dir
            continue
        if name == pardir:
            # parent dir
            if path:
                path, name = split(path)
                if name == pardir:
                    path = join(path, pardir, pardir)
            else:
                path = pardir
            continue
        newpath = join(path, name)
        if not islink(newpath):
            path = newpath
            continue
        # Resolve the symbolic link
        if newpath in seen:
            # Already seen this path
            path = seen[newpath]
            if path is not None:
                # use cached value
                continue
            # The symlink is not resolved, so we must have a symlink loop.
            # Return already resolved part + rest of the path unchanged.
            return join(newpath, rest), False
        seen[newpath] = None  # not resolved symlink
        path, ok = _joinrealpath(path, os.readlink(newpath), seen)
        if not ok:
            return join(path, rest), False
        seen[newpath] = path  # resolved symlink

    return path, True
