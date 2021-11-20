# make sure imported modules don't break package installs
import os

name = 'floob'
version = '1.2.0'
authors = ["joe.bloggs"]
uuid = "156730d7122441e3a5745cc81361f49a"
description = "floobtasticator"

private_build_requires = ["build_util"]

def commands():
    env.PYTHONPATH.append('{root}/python')

build_command = 'python {root}/build.py {install}'
