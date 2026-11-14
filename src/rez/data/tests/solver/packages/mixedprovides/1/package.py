# a package whose first variant provides its own python  while the second
# variant depends on a real python
name = "mixedprovides"
version = "1"

variants = [
    [".provides.python-2.6"],
    ["python-2.7"],
]
