name = "pre_test_package"

version = "1.0.0"

tests = {
    "foo": "echo foo",
    "bar": "echo bar",
}


def pre_test_commands():
    if test.name == "foo":
        env.IS_FOO_TEST.set(1)
