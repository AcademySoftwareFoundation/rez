"""
Misc useful stuff.
"""
import stat
import sys
import os
import shutil
import time
import posixpath
import ntpath
import UserDict

WRITE_PERMS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH

def gen_dotgraph_image(dot_data, out_file):

    # shortcut if writing .dot file
    if out_file.endswith(".dot"):
        with open(out_file, 'w') as f:
            f.write(dot_data)
        return

    import pydot
    graph = pydot.graph_from_dot_data(dot_data)

    # assume write format from image extension
    ext = "jpg"
    if '.' in out_file:
        ext = out_file.rsplit('.', 1)[-1]

    try:
        fn = getattr(graph, "write_" + ext)
    except Exception:
        sys.stderr.write("could not write to '" + out_file + "': unknown format specified")
        sys.exit(1)

    fn(out_file)


def readable_time_duration(secs, approx=True, approx_thresh=0.001):
    divs = ((24 * 60 * 60, "days"), (60 * 60, "hours"), (60, "minutes"), (1, "seconds"))

    if secs == 0:
        return "0 seconds"
    neg = (secs < 0)
    if neg:
        secs = -secs

    results = []
    remainder = secs
    for seconds, label in divs:
        value, remainder = divmod(remainder, seconds)
        if value:
            results.append((value, label))
            if approx and (float(remainder) / secs) >= approx_thresh:
                # quit if remainder drops below threshold
                break
    s = ', '.join(['%d %s' % x for x in results])

    if neg:
        s = '-' + s
    return s

def hide_local_packages():
    import rez.filesys
    rez.filesys._g_syspaths = rez.filesys._g_syspaths_nolocal

def unhide_local_packages():
    import rez.filesys
    rez.filesys._g_syspaths = rez.filesys.get_system_package_paths()

def remove_write_perms(path):
    st = os.stat(path)
    mode = st.st_mode & ~WRITE_PERMS
    os.chmod(path, mode)

def copytree(src, dst, symlinks=False, ignore=None, hardlinks=False):
    '''
    copytree that supports hard-linking
    '''
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if hardlinks:
        def copy(srcname, dstname):
            try:
                # try hard-linking first
                os.link(srcname, dstname)
            except OSError:
                shutil.copy2(srcname, dstname)
    else:
        copy = shutil.copy2

    os.makedirs(dst)
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
        errors.extend((src, dst, str(why)))
    if errors:
        raise shutil.Error(errors)

def get_epoch_time():
    """
    get time since the epoch as an int
    """
    return int(time.mktime(time.localtime()))

def safe_chmod(path, mode):
    "set the permissions mode on path, but only if it differs from the current mode."
    if stat.S_IMODE(os.stat(path).st_mode) != mode:
        os.chmod(path, mode)

def to_nativepath(path):
    return os.path.join(path.split('/'))

def to_ntpath(path):
    return ntpath.sep.join(path.split(posixpath.sep))

def to_posixpath(path):
    return posixpath.sep.join(path.split(ntpath.sep))

class AttrDict(dict):
    """
    A dictionary with attribute-based lookup.
    """
    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def copy(self):
        return AttrDict(dict.copy(self))

class AttrDictWrapper(UserDict.UserDict):
    """
    Wrap a custom dictionary with attribute-based lookup.
    """
    def __init__(self, data):
        self.__dict__['data'] = data

    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self.data
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

    def __setattr__(self, attr, value):
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            super(AttrDictWrapper, self).__setattr__(attr, value)
        self.data[attr] = value
