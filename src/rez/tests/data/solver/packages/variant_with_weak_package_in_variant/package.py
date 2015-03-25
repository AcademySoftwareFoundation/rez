name = 'variant_with_weak_package_in_variant'
version = '1'
authors = ["oops"]
uuid = "2b95f39c-1ae2-4080-a7a7-3f2062e5a65d"
description = "package with a weak ref in the variant"
variants = [
    ["bah-1.0.0"],
    ["bah-1.0.1"],
    ["~bah-2.0.0"]]
