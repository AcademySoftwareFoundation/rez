# pyright: reportUndefinedVariable=false
name = "shell"

version = "1.0.0"


def commands():
    env.PATH.append("{root}")
