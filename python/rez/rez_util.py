"""
Misc useful stuff.
"""
import stat
import sys
import os
import shutil

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
    if(out_file.rfind('.') != -1):
        ext = out_file.split('.')[-1]

    try:
        fn = getattr(graph, "write_"+ext)
    except Exception:
        sys.stderr.write("could not write to '" + out_file + "': unknown format specified")
        sys.exit(1)

    fn(out_file)


def readable_time_duration(secs, approx=True):
    divs = ((24*60*60, "days"), (60*60, "hours"), (60, "minutes"), (1, "seconds"))

    if secs == 0:
        return "0 seconds"
    neg = (secs < 0)
    if neg:
        secs = -secs

    if approx:
        for i,s in enumerate([x[0] for x in divs[:-1]]):
            ss = float(s) * 0.9
            if secs >= ss:
                n = secs / s
                frac = float((secs+s) % s) / float(s)
                if frac < 0.1:
                    secs = n * s
                elif frac > 0.9:
                    secs = (n+1) * s
                else:
                    s2 = divs[i+1][0]
                    secs -= secs % s2
                break

    toks = []
    for d in divs:
        if secs >= d[0]:
            n = secs/d[0]
            count = n*d[0]
            label = d[1]
            if n == 1:
                label = label[:-1]
            toks.append((n, label))
            secs -= count

    s = str(", ").join([("%d %s" % (x[0],x[1])) for x in toks])
    if neg:
        s = '-' + s
    return s

def hide_local_packages():
    import os
    localpath = os.getenv("REZ_LOCAL_PACKAGES_PATH").strip()
    if localpath:
        pkgpaths = os.getenv("REZ_PACKAGES_PATH","").strip().split(':')
        if localpath in pkgpaths:
            pkgpaths.remove(localpath)
 
def remove_write_perms(path):
    import os
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
