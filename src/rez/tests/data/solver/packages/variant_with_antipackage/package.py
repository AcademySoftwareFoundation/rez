name = 'variant_with_antipackage'
version = '1'
authors = ["oops"]
uuid = "ca952d6d-5eec-46f7-a8fd-31aa95c826b7"
description = "package with an antipackage in the variant"
variants = [
    ["bah-1.0.0"],
    ["bah-1.0.1"],
    ["!bah-2.0.0"]]
