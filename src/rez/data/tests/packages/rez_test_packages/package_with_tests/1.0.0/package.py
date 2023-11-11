name = "package_with_tests"

version = "1.0.0"

variants = [["python-3"], ["python-2"]]

tests = {
    "foo": {
        "command": "echo foo",
        "requires": ["python-2.7"],
    },
    "fizz": {
        "command": "echo another",
        "requires": ["python-2.3+"],
    },
    "bar": {
        "command": "echo foo",
        "requires": ["python-3.8"],
    },
    "buzz": {
        "command": "echo buzz",
        "requires": ["python-3.7+"],
    },
    "invalid_test": {
        "command": "echo invalid_test",
        "requires": ["python-4"],  # python-4 exists but is **not** in ``variants``
    },
    "lastly": {
        "command": "echo lastly",
        "requires": ["python-3"],
        "run_on": "explicit",
    },
    "on_variants_test_name": {
        "command": "echo on_variants_test_name",
        "on_variants": {
            "type": "requires",
            "value": ["python-2"],
        },
        "requires": ["dependency-1+"],
    },
}
