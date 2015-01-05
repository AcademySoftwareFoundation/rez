# The name of the project
name = "hello_world"

# The version of the project. You don't have to use major.minor.patch - use
# whatever is most appropriate to your project.
version = "1.0.0"

# The author(s) of the project
authors = ["ajohns"]

# A meaningful description of the project. NOT a description of this specific
# package version, but an overall, general description of the project itself.
description = \
    """
    A minimal example python project.
    """

# Any executables that the project provides
tools = ["hello"]

# Dependencies of the project. It is IMPORTANT that you properly version these
# dependencies. If your requirements are too loose, a new release of a dependency
# could break your project, and that would be YOUR fault. If your requirements
# are too strict, you will need to release new versions of the project more often
# than you would otherwise need to.
requires = ["python"]

# Where to find documentation. If you provide this, people can get to your docs
# either using the 'rez-help' commandline tool, or via the Rez GUI. If a single
# string is provided, it is assumed to be a URL and will be opened using a web
# browser. If multiple arguments are provided (a string containing spaces), it
# is assumed to be a command and will be run as-is.
help = "file://{root}/help.html"

# This is a unique ID for this project (not specifically for this version, but
# for the project as a whole). It is here to stop two different packages that
# happen to have the same name, from being released as the same package. If you
# need to generate one, you can run this command:
# ]$ python -c 'import uuid; print uuid.uuid4().hex'
uuid = "d3d469dd90954f29b2744f5568723a66"

# What your project needs to do to configure itself for the target environment.
# This is a typical example - a path containing python source is appended to
# $PYTHONPATH, and a path containing executables is appended to $PATH. This is
# python code, using a mini-API dedicated to doing things such as altering
# environment variables, creating aliases and so on. The API is called 'Rex', see
# the Rez documentation for more extensive examples.
def commands():
    env.PYTHONPATH.append("{root}/python")
    env.PATH.append("{root}/bin")
