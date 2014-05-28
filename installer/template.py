#! /usr/bin/env python

sources = """
@SOURCES@"""

import os
import sys
import base64
import tempfile
import shutil


def unpack(sources):
    temp_dir = tempfile.mkdtemp(prefix='rez-get-')
    for relpath, content in sources.items():
        dirpath, filename = os.path.split(relpath)
        dir_ = os.path.join(temp_dir, dirpath)
        if not os.path.isdir(dir_):
            os.makedirs(dir_)

        with open(os.path.join(dir_, filename), 'w') as f:
            f.write(content)
    return temp_dir


def bootstrap():
    #@ENTRY@
    pass


if __name__ == "__main__":
    import pickle
    sources = pickle.loads(base64.decodestring(sources))

    try:
        temp_dir = unpack(sources)
        os.chdir(temp_dir)
        sys.path.insert(0, temp_dir)
        bootstrap()
    finally:
        shutil.rmtree(temp_dir)
