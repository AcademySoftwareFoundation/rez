# This deliberately raises an exception, because we do not expect it to be
# loaded in the unit test - yaml_packages/versioned/2.0 will take precedence.
raise Exception("This package.py should never be loaded")
