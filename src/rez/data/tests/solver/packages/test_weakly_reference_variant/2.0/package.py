name = "test_weakly_reference_variant"
version = "2.0"

requires = ["~pyfoo"]

variants = [["test_variant_split_mid1", "~test_variant_split_mid2-1..3"]]
