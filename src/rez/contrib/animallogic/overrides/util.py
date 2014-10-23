import os
from functools import wraps

ANIMAL_LOGIC_SEPARATORS = {
                           "CMAKE_MODULE_PATH":"\';\'", 
                           "AL_MAYA_AUTO_PYEVAL":" ", 
                           "AL_MAYA_AUTO_LOADVERSIONEDTOOL":" ", 
                           "ARTISTTOOLPALETTE_TOOLS":","
}

FILESYSTEM_CHARACTER_MAPPING = (
    ("!", "_not_"),
    ("+<", "_thru_"),
    ("+", "_ge_"), 
    ("<", "_lt_"),
    ("~", "_weak_"),
)

def encode_filesystem_name(wrapped):
    """
    The current implementation of rez.utils.encode_filesystem_name produces 
    backwards incompatible paths which is unsuitable for our needs.  We override
    this behaviour here to provide compatibility with rez 1.7.
    """

    @wraps(wrapped)
    def wrapper(input_):

        for original, replacement in FILESYSTEM_CHARACTER_MAPPING:
            input_ = input_.replace(original, replacement)

        return input_

    return wrapper

def decode_filesystem_name(wrapped):
    """
    The current implementation of rez.utils.decode_filesystem_name is 
    incompatible with our changes to rez.utils.encode_filesystem_name.  We 
    override this behaviour here to provide compatibility with rez 1.7.
    """

    @wraps(wrapped)
    def wrapper(input_):

        for replacement, original in FILESYSTEM_CHARACTER_MAPPING:
            input_ = input_.replace(original, replacement)

        return input_

    return wrapper

def convert_old_commands(wrapped):
    """
    The CMAKE_MODULE_PATH environment variable uses a non-standard ';' separator
    (note the ' are part of the separator) which is not handled correctly by the
    rez.utils.convert_old_commands function.  This override intercepts this 
    environment variable in the command list and patches it accordingly.
    """

    @wraps(wrapped)
    def wrapper(commands, annotate=True):

        for index, command in enumerate(commands):
            if command.startswith("export "):
                variable, value = command.split(' ', 1)[1].split('=', 1)
                if variable in ANIMAL_LOGIC_SEPARATORS:
                    separator = ANIMAL_LOGIC_SEPARATORS[variable]
                    commands[index] = command.replace(separator, os.pathsep)

        return wrapped(commands, annotate=annotate)

    return wrapper

