name = 'anti'
version = '1.0.0'
authors = ["joe.bloggs"]
uuid = "e760fa04-043d-47bb-ba4d-543b18a70959"
description = "package with anti package"


private_build_requires = ["build_util"]
requires = ["floob", "!loco"]

def commands():
    env.PYTHONPATH.append('{root}/python')

build_command = 'python {root}/build.py {install}'
