name = 'two_packages_in_variant_unsorted'
version = '1'
authors = ["oops"]
uuid = "1c84af87-db67-4734-a1f0-f1a09e3f0dbe"
description = "package with two packages in variants "
variants = [
    ["bah-1.0.1", "eek-1.0.1"],
    ["bah-1.0.1", "eek-2.0.0"],
    ["bah-2.0.0", "eek-1.0.0"],
    ["bah-2.0.0", "eek-1.0.1"],
    ["bah-1.0.0", "eek-1.0.1"],
    ["bah-1.0.0", "eek-2.0.0"]]


