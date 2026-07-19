# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Filesystem-related utilities.
"""
from __future__ import annotations

from threading import Lock
from tempfile import mkdtemp
from contextlib import contextmanager
from uuid import uuid4
import errno
import sys
import weakref
import atexit
import posixpath
import ntpath
import os.path
import shutil
import os
import stat
import platform
import uuid

from rez.utils.platform_ import platform_
from rez.util import which
from rez.utils.execution import Popen

is_windows = platform.system() == "Windows"
is_mac = platform.system() == "Darwin"


class TempDirs(object):
    """Tempdir manager.

    Makes tmpdirs and ensures they're cleaned up on program exit.
    """
    instances_lock = Lock()
    instances = []

    def __init__(self, tmpdir, prefix="rez_") -> None:
        self.tmpdir = tmpdir
        self.prefix = prefix
        self.dirs = set()
        self.lock = Lock()

        with TempDirs.instances_lock:
            TempDirs.instances.append(weakref.ref(self))

    def mkdtemp(self, cleanup: bool = True):
        path = mkdtemp(dir=self.tmpdir, prefix=self.prefix)
        if not cleanup:
            return path

        with self.lock:
            self.dirs.add(path)

        return path

    def __del__(self) -> None:
        self.clear()

    def clear(self) -> None:
        with self.lock:
            if not self.dirs:
                return

            dirs = self.dirs
            self.dirs = set()

        for path in dirs:
            if os.path.exists(path) and not os.getenv("REZ_KEEP_TMPDIRS"):
                safe_rmtree(path)

    @classmethod
    def clear_all(cls) -> None:
        with TempDirs.instances_lock:
            instances = cls.instances[:]

        for ref in instances:
            instance = ref()
            if instance is not None:
                instance.clear()


atexit.register(TempDirs.clear_all)


@contextmanager
def make_path_writable(path):
    """Temporarily make `path` writable, if possible.

    Args:
        path (str): Path to make temporarily writable
    """
    try:
        orig_mode = os.stat(path).st_mode
        new_mode = orig_mode

        if not os.access(path, os.W_OK):
            new_mode = orig_mode | stat.S_IWUSR

        # make writable
        if new_mode != orig_mode:
            os.chmod(path, new_mode)

    except OSError:
        # ignore access errors here, and just do nothing. It will be more
        # intuitive for the calling code to fail on access instead.
        #
        orig_mode = None
        new_mode = None

    # yield, then reset mode back to original
    try:
        yield
    finally:
        if new_mode != orig_mode:
            os.chmod(path, orig_mode)


@contextmanager
def retain_cwd():
    """Context manager that keeps cwd unchanged afterwards.
    """
    cwd = os.getcwd()
    try:
        yield
    finally:
        os.chdir(cwd)


def get_existing_path(path, topmost_path=None):
    """Get the longest parent path in `path` that exists.

    If `path` exists, it is returned.

    Args:
        path (str): Path to test
        topmost_path (str): Do not test this path or above

    Returns:
        str: Existing path, or None if no path was found.
    """
    prev_path = None

    if topmost_path:
        topmost_path = os.path.normpath(topmost_path)

    while True:
        if os.path.exists(path):
            return path

        path = os.path.dirname(path)
        if path == prev_path:
            return None

        if topmost_path and os.path.normpath(path) == topmost_path:
            return None

        prev_path = path


def safe_listdir(path):
    """Safe listdir.

    Works in a multithread/proc scenario where dirs may be deleted at any time
    """
    try:
        return os.listdir(path)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return []
        raise


def safe_remove(path):
    """Safely remove the given file or directory.

    Works in a multithreaded scenario.
    """
    if not os.path.exists(path):
        return

    try:
        if os.path.isdir(path) and not os.path.islink(path):
            safe_rmtree(path)
        else:
            os.remove(path)
    except OSError:
        if os.path.exists(path):
            raise


def forceful_rmtree(path) -> None:
    """Like shutil.rmtree, but may change permissions.

    Specifically, non-writable dirs within `path` can cause rmtree to fail. This
    func chmod's to writable to avoid this issue, if possible.

    Also handled:
        * path length over 259 char (on Windows)
        * unicode path
        * AppleDouble resource forks
    """

    def _on_error(func, path, exc_info) -> None:
        if is_mac and exc_info[0] is FileNotFoundError and os.path.basename(path).startswith("._"):
            # Assume if we are on a mac and the file starts with a "._" it is a resource fork and the
            # corresponding data fork has been removed.  Since we are removing the whole directory tree
            # it should not be a problem.
            return
        try:
            if is_windows:
                path = windows_long_path(path)

            parent_path = os.path.dirname(path)
            if not os.access(parent_path, os.W_OK):
                st = os.stat(parent_path)
                os.chmod(parent_path, st.st_mode | stat.S_IWUSR)

            if not os.access(path, os.W_OK):
                st = os.stat(path)
                os.chmod(path, st.st_mode | stat.S_IWUSR)

        except:
            # avoid confusion by ensuring original exception is reraised
            pass

        func(path)

    shutil.rmtree(path, onerror=_on_error)


def safe_rmtree(path) -> None:
    """Like shutil.rmtree, but handles race condition caused by AppleDouble files.

    On Mac OSX files may consist of a data fork and a resource fork.  On a foreign file system these files
    are stored as AppleDouble files.  The data fork is stored as "filename" and the resource fork is stored
    as "._filename".  When the data fork is removed the corresponding resource fork is also removed.  This
    results in a FileNotFoundError when `shutil.rmtree` tries to remove the resource fork.  This is addressed
    in Python 13.3 for another situation not related to AppleDouble files
    (https://github.com/python/cpython/pull/14064)
    """

    def _on_error(_func, path, exc_info):
        if not is_mac or exc_info[0] is not FileNotFoundError or not os.path.basename(path).startswith("._"):
            raise exc_info[1].with_traceback(exc_info[2])

    shutil.rmtree(path, onerror=_on_error)


def replacing_symlink(source, link_name) -> None:
    """Create symlink that overwrites any existing target.
    """
    with make_tmp_name(link_name) as tmp_link_name:
        os.symlink(source, tmp_link_name)
        replace_file_or_dir(link_name, tmp_link_name)


def replacing_copy(src, dest, follow_symlinks: bool = False) -> None:
    """Perform copy that overwrites any existing target.

    Will copy/copytree `src` to `dest`, and will remove `dest` if it exists,
    regardless of what it is.

    If `follow_symlinks` is False, symlinks are preserved, otherwise their
    contents are copied.

    Note that this behavior is different to `shutil.copy`, which copies src
    into dest if dest is an existing dir.
    """
    with make_tmp_name(dest) as tmp_dest:
        if os.path.islink(src) and not follow_symlinks:
            # special case - copy just a symlink
            src_ = os.readlink(src)
            os.symlink(src_, tmp_dest)
        elif os.path.isdir(src):
            # copy a dir
            shutil.copytree(src, tmp_dest, symlinks=(not follow_symlinks))
        else:
            # copy a file
            shutil.copy2(src, tmp_dest)

        replace_file_or_dir(dest, tmp_dest)


def replace_file_or_dir(dest, source):
    """Replace `dest` with `source`.

    Acts like an `os.rename` if `dest` does not exist. Otherwise, `dest` is
    deleted and `src` is renamed to `dest`.
    """
    from rez.vendor.atomicwrites import replace_atomic

    if not os.path.exists(dest):
        try:
            rename(source, dest)
            return
        except:
            if not os.path.exists(dest):
                raise

    try:
        replace_atomic(source, dest)
        return
    except:
        pass

    with make_tmp_name(dest) as tmp_dest:
        rename(dest, tmp_dest)
        rename(source, dest)


def additive_copytree(src, dst, symlinks: bool = False, ignore=None) -> None:
    """Version of `copytree` that merges into an existing directory.
    """
    os.makedirs(dst, exist_ok=True)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        if os.path.isdir(s):
            additive_copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


@contextmanager
def make_tmp_name(name):
    """Generates a tmp name for a file or dir.

    This is a tempname that sits in the same dir as `name`. If it exists on
    disk at context exit time, it is deleted.
    """
    path, base = os.path.split(name)

    # there's a reason this isn't a hidden file:
    # https://github.com/AcademySoftwareFoundation/rez/pull/1088
    #
    tmp_base = "_tmp-%s-%s" % (base, uuid4().hex)

    tmp_name = os.path.join(path, tmp_base)

    try:
        yield tmp_name
    finally:
        safe_remove(tmp_name)


def is_subdirectory(path_a, path_b) -> bool:
    """Returns True if `path_a` is a subdirectory of `path_b`."""
    path_a = real_path(path_a)
    path_b = real_path(path_b)
    try:
        relative = os.path.relpath(path_a, path_b)
    except ValueError:
        # Different mounts on Windows:
        # ValueError: path is on mount 'c:', start on mount 'd:'
        #
        return False

    return not relative.startswith(os.pardir + os.sep)


def find_matching_symlink(path: str, source: str) -> str | None:
    """Find a symlink under `path` that points at `source`.

    If source is relative, it is considered relative to `path`.

    Returns:
        str: Name of symlink found, or None.
    """
    def to_abs(target):
        if os.path.isabs(target):
            return target
        else:
            return os.path.normpath(os.path.join(path, target))

    abs_source = to_abs(source)

    for name in os.listdir(path):
        linkpath = os.path.join(path, name)
        if os.path.islink(linkpath):
            source_ = os.readlink(linkpath)
            if to_abs(source_) == abs_source:
                return name

    return None


def copy_or_replace(src: str, dst: str):
    '''try to copy with mode, and if it fails, try replacing
    '''
    try:
        shutil.copy(src, dst)
        return

    except (OSError, IOError) as e:
        # It's possible that the file existed, but was owned by someone
        # else - in that situation, shutil.copy might then fail when it
        # tries to copy perms.
        # However, it's possible that we have write perms to the dir -
        # in which case, we can just delete and replace
        #
        if e.errno != errno.EPERM:
            raise

    # try copying into a temporary location beside the old file - if we have
    # perms to do that, we should have perms to then delete the old file, and
    # move the new one into place
    #
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))

    dst_dir, dst_name = os.path.split(dst)
    tmp_filename = ".%s.%s" % (uuid.uuid4().hex, dst_name)
    dst_temp = os.path.join(dst_dir, tmp_filename)

    shutil.copy(src, dst_temp)

    if not os.path.isfile(dst_temp):
        raise RuntimeError(
            "shutil.copy completed successfully, but path"
            " '%s' still did not exist" % dst_temp
        )
    os.remove(dst)
    shutil.move(dst_temp, dst)


def copytree(src: str, dst: str, symlinks: bool = False, ignore=None, hardlinks: bool = False):
    '''copytree that supports hard-linking
    '''
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if hardlinks:
        def copy(srcname, dstname) -> None:
            try:
                # try hard-linking first
                os.link(srcname, dstname)
            except OSError:
                shutil.copy2(srcname, dstname)
    else:
        copy = shutil.copy2  # type: ignore[assignment]

    os.makedirs(dst, exist_ok=True)

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy(srcname, dstname)
        # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except shutil.WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.append((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)


def movetree(src: str, dst: str) -> None:
    """Attempts a move, and falls back to a copy+delete if this fails
    """
    try:
        shutil.move(src, dst)
    except:
        copytree(src, dst, symlinks=True, hardlinks=True)
        safe_rmtree(src)


def safe_chmod(path: str, mode) -> None:
    """Set the permissions mode on path, but only if it differs from the current mode.
    """
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)


def to_nativepath(path: str):
    path = path.replace('\\', '/')
    return os.path.join(*path.split('/'))


def to_ntpath(path: str):
    return ntpath.sep.join(path.split(posixpath.sep))


def to_posixpath(path: str):
    return posixpath.sep.join(path.split(ntpath.sep))


_WINDOWS_MAX_PATH = 259  # Win32 MAX_PATH minus the null terminator

# Reparse tag constant for Windows junctions (mount points).  Defined in
# ntifs.h as IO_REPARSE_TAG_MOUNT_POINT.  We hardcode it because it is not
# exposed in Python's stat module on all versions.
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


def _is_link_or_junction(path: str) -> bool:
    """Return True if ``path`` is a symlink or a Windows junction point.

    ``os.path.islink`` detects symlinks on all Python versions but does NOT
    detect junctions on any version (it checks for
    ``IO_REPARSE_TAG_SYMLINK`` only).  ``os.path.isjunction`` (3.12+) covers
    junctions; for 3.8-3.11 we fall back to checking ``st_reparse_tag`` on
    ``os.lstat``.
    """
    if os.path.islink(path):
        return True
    # os.path.isjunction was added in Python 3.12.
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None:
        return isjunction(path)
    # Python 3.8-3.11: detect junctions via the reparse tag on lstat.
    # st_reparse_tag is non-zero when the path is a reparse point; we
    # check for the mount-point tag specifically.
    try:
        st = os.lstat(path)
    except OSError:
        return False
    tag = getattr(st, "st_reparse_tag", 0)
    return tag == _IO_REPARSE_TAG_MOUNT_POINT


def _windows_realpath(path: str) -> str:
    """Resolve symlinks and junctions on Windows without expanding mapped drives.

    ``os.path.realpath`` on Python 3.8+ Windows uses ``GetFinalPathNameByHandle``
    which expands mapped drive letters (e.g. ``N:\\``) to their underlying UNC
    server paths.  This function resolves only actual filesystem symlinks and
    junction points, walking the path component-by-component so that the drive
    root (drive-letter or UNC prefix) is never touched.

    When a symlink resolves to an absolute path, the target's prefix components
    are re-walked from the root so that intermediate-directory symlinks are
    resolved transitively (matching POSIX ``os.path.realpath`` semantics).
    """
    path = os.path.normpath(os.path.abspath(path))
    drive, rest = os.path.splitdrive(path)
    # Preserve the root separator so UNC paths keep their leading "\\" and
    # drive-letter paths keep their "\".
    root = drive + (os.sep if rest.startswith(os.sep) else "")

    # Component stack: we process left-to-right, but when a symlink resolves
    # to an absolute path we push its components onto the front so that any
    # intermediate-directory symlinks in the target are re-walked.
    components = rest.lstrip(os.sep).split(os.sep)
    components = [c for c in components if c]
    result = root
    total_depth = 0

    while components:
        part = components.pop(0)
        candidate = os.path.join(result, part)
        depth = 0
        while _is_link_or_junction(candidate) and depth < 40:
            target = os.readlink(candidate)
            # os.readlink on Windows may return an extended-length path
            # (\\?\C:\... or \\?\UNC\server\share\...). Strip the prefix so
            # we can work with ordinary path strings.
            if target.startswith("\\\\?\\UNC\\"):
                target = "\\\\" + target[8:]
            elif target.startswith("\\\\?\\"):
                target = target[4:]
            if not os.path.isabs(target):
                target = os.path.join(os.path.dirname(candidate), target)
            # For paths that exceed MAX_PATH, re-add the extended-length
            # prefix before calling abspath so the Win32 API (GetFullPathNameW)
            # can handle the length on hosts without LongPathsEnabled in the
            # registry.  We strip the prefix again afterwards so the rest of
            # the walk operates on ordinary path strings.
            if len(target) > _WINDOWS_MAX_PATH:
                if target.startswith("\\\\"):
                    target = "\\\\?\\UNC\\" + target[2:]
                else:
                    target = "\\\\?\\" + target
                candidate = os.path.abspath(target)
                if candidate.startswith("\\\\?\\UNC\\"):
                    candidate = "\\\\" + candidate[8:]
                elif candidate.startswith("\\\\?\\"):
                    candidate = candidate[4:]
                candidate = os.path.normpath(candidate)
            else:
                candidate = os.path.normpath(os.path.abspath(target))
            depth += 1
            total_depth += 1
            if total_depth >= 40:
                break

        # If the symlink resolved to an absolute path, its prefix components
        # may themselves contain symlinks that haven't been walked.  Re-walk
        # the entire resolved path from its root by pushing its components
        # back onto the stack.  This handles the case where, e.g., /a/b is a
        # symlink to /x/y and /x is itself a symlink.
        #
        # Guard against symlink loops: if the global resolution budget is
        # exhausted, stop re-walking and accept the current candidate.
        if candidate != os.path.join(result, part) and total_depth < 40:
            t_drive, t_rest = os.path.splitdrive(candidate)
            t_root = t_drive + (os.sep if t_rest.startswith(os.sep) else "")
            new_parts = [c for c in t_rest.lstrip(os.sep).split(os.sep) if c]
            root = t_root
            result = t_root
            components = new_parts + components
            continue

        result = candidate
    return result


def canonical_path(path: str, platform=None):
    """Return a normalised path suitable for identity comparison.

    Resolves symlinks (on non-Windows), lowercases on case-insensitive
    filesystems, and normalises separators.  Two paths that refer to the
    same location will compare equal (``==``) after canonicalisation.

    Use this when the question is "do these two paths refer to the same
    thing?" - e.g. deduplicating package repository locations, or
    checking whether a loaded resource path matches a stored location.

    Do not use this when you need a path to open a file, pass to an
    external tool, or store in a bundle/context that may be read on
    another platform - the lowercasing it applies on case-insensitive
    filesystems mutates the string and can break case-sensitive consumers
    (e.g. a Linux NFS mount accessed from a Windows client).  Use
    :func:`real_path` for those cases instead.

    Args:
        path (str): Filepath being formatted
        platform (rez.utils.platform_.Platform): Indicates platform path is being
            formatted for. Defaults to current platform.

    Returns:
        str: Provided path, formatted for platform.
    """
    if platform is None:
        platform = platform_

    # On Windows, os.path.realpath from py3.8 onwards silently converts drive
    # lettered paths to their UNC equivalents (N:\ -> \\server\share\).
    # We check sys.platform rather than the platform argument because this is
    # an OS-level behaviour of os.path.realpath, not a user-configurable choice.
    if sys.platform == "win32":
        # Lazy import avoids a circular dependency (config imports filesystem).
        from rez.config import config  # noqa: PLC0415
        if config.resolve_links_on_windows:
            path = _windows_realpath(path)
        else:
            # Default: abspath preserves the caller's path form (drive-letter
            # stays drive-letter, UNC stays UNC) and restores the pre-3.8
            # behaviour where realpath on Windows was equivalent to abspath.
            path = os.path.normpath(os.path.abspath(path))
    else:
        path = os.path.normpath(os.path.realpath(path))

    if not platform.has_case_sensitive_filesystem:
        return path.lower()

    return path


def real_path(path: str) -> str:
    r"""Return an absolute, form-stable path for file I/O and path operations.

    Resolves relative segments and (on non-Windows) symlinks, while
    preserving the form of the input path - a drive-letter path stays
    drive-letter; a UNC path stays UNC.

    Use this when you need a stable absolute path to use rather than to
    compare - opening a file, building a cache key, passing to
    ``os.path.relpath``, returning a path to the user, or storing a path
    in a serialised format that may be read on another platform.

    Do not use this when the question is "do these two paths refer to
    the same filesystem location?" - use :func:`canonical_path` instead,
    which lowercases on case-insensitive filesystems so that equality
    checks work regardless of capitalisation.

    Justification: ``os.path.realpath`` on Windows (Python 3.8+)
    silently expands mapped drive-letter paths to their UNC
    equivalents (``N:\\ `` -> ``\\server\share\``).  That expansion
    breaks ``os.path.relpath`` across mismatched UNC roots
    (``ValueError``), corrupts cache keys, and mutates capitalisation
    in stored paths. ``os.path.abspath`` avoids this while still
    making paths absolute and normalising separators.

    Returns:
        str: Absolute path with the same drive-letter / UNC form as input.
    """
    if sys.platform == "win32":
        return os.path.normpath(os.path.abspath(path))
    return os.path.realpath(path)


def walk_up_dirs(path: str):
    """Yields absolute directories starting with the given path, and iterating
    up through all it's parents, until it reaches a root directory"""
    prev_path = None
    current_path = os.path.abspath(path)
    while current_path != prev_path:
        yield current_path
        prev_path = current_path
        current_path = os.path.dirname(prev_path)


def windows_long_path(dos_path: str):
    """Prefix '\\?\' for path longer than 259 char (Win32API limitation)
    """
    path = os.path.abspath(dos_path)

    if path.startswith("\\\\?\\"):
        pass
    elif path.startswith("\\\\"):
        path = "\\\\?\\UNC\\" + path[2:]
    else:
        path = "\\\\?\\" + path

    return path


def rename(src: str, dst: str):
    """Utility function to rename a file or folder src to dst with retrying.

    This function uses the built-in `os.rename()` function and falls back to `robocopy` tool
    if `os.rename` raises a `PermissionError` exception.

    Args:
        src (str): The original name (path) of the file or folder.
        dst (str): The new name (path) for the file or folder.

    Raises:
        OSError: If renaming fails after all attempts.

    """
    # Inspired by https://github.com/conan-io/conan/blob/2.1.0/conan/tools/files/files.py#L207
    try:
        os.rename(src, dst)
    except PermissionError as err:
        if is_windows and which("robocopy") and os.path.isdir(src):
            # https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy
            args = [
                "robocopy",
                # /move Moves files and directories, and deletes them from the source after they are copied.
                "/move",
                # /e Copies subdirectories. Note that this option includes empty directories.
                "/e",
                # /ndl Specifies that directory names are not to be logged.
                "/ndl",
                # /nfl Specifies that file names are not to be logged.
                "/nfl",
                # /njs Specifies that there's no job summary.
                "/njs",
                # /njh Specifies that there's no job header.
                "/njh",
                # /np Specifies that the progress of the copying operation
                # (the number of files or directories copied so far) won't be displayed.
                "/np",
                # /ns Specifies that file sizes aren't to be logged.
                "/ns",
                # /nc Specifies that file classes aren't to be logged.
                "/nc",
                src,
                dst,
            ]
            process = Popen(args)
            process.communicate()
            if process.returncode > 7:  # https://ss64.com/nt/robocopy-exit.html
                raise OSError("Rename {} to {} failed.".format(src, dst))
        else:
            raise err
