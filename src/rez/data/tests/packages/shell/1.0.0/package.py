# pyright: reportUndefinedVariable=false
name = "shell"

version = "1.0.0"


def commands():
    import os

    env.PATH.append("{root}")
    env.PYTHONPATH.append(os.path.join("{root}", "src"))
    env.PYTHONPATH.append(os.path.join("{root}", "python"))
    env.CMAKE_MODULE_PATH.append(os.path.join(this.root, "foo.cmake"))
    env.CMAKE_MODULE_PATH.append(os.path.join(this.root, "bar.cmake"))
