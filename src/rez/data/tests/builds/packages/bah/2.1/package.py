name = 'bah'
version = '2.1'
authors = ["joe.bloggs"]
uuid = "3c027ce6593244af947e305fc48eec96"
description = "bah humbug"

private_build_requires = ["build_util"]

variants = [
    ["foo-1.0"],
    ["foo-1.1"]]

hashed_variants = True

build_command = 'python {root}/build.py {install}'
