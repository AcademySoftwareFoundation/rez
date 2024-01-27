name = 'foo'
version = '1.1.0'
authors = ["joe.bloggs"]
uuid = "8031b8a1b1994ea8af86376647fbe530"
description = "foo thing"

build_requires = ["floob"]

private_build_requires = ["build_util", "python"]

@include("late_utils")
def commands():
    # Test prepends by throwing in an extra python path
    env.PYTHONPATH.prepend('{root}/python')
    env.PYTHONPATH.append('{root}/noexist')
    env.FOO_IN_DA_HOUSE = "1"

    late_utils.add_eek_var(env)

build_command = 'python {root}/build.py {install}'
