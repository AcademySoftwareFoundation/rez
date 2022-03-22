name = 'build_util'
version = '1'
authors = ["joe.bloggs"]
uuid = "9982b60993af4a4d89e8372472a49d02"
description = "build utilities"

def commands():
    env.PYTHONPATH.append('{root}/python')

build_command = 'python {root}/build.py {install}'
