name = 'loco'
version = '3'
authors = ["joe.bloggs"]
uuid = "4e9f63cbc4794453b0031f0c5ff50759"
description = "muy loco"

# deliberate conflict
requires = ["foo-1.0", "foo-1.1"]

build_command = "python {root}/build.py {install}"
