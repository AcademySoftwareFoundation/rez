
ANIMAL_LOGIC_SEPARATORS = {
                           "AL_MAYA_AUTO_PYEVAL":" ", 
                           "AL_MAYA_AUTO_LOADVERSIONEDTOOL":" ", 
                           "ARTISTTOOLPALETTE_TOOLS":",",
                           "CMAKE_MODULE_PATH":";",
                           "AL_PYTHON_LIBS_JOBS_LIST":",", 
                           "AL_PYAPPS_LIST":",", 
                           "AL_PYLIBS_LIST":",", 
                           "AL_XSI_AUTO_LOADVERSIONEDTOOL":",", 
                           "ARENA_MODULE_PATH":",",
                           "DOXYGEN_TAGFILES":" ",
}


FILESYSTEM_CHARACTER_MAPPING = (
    ("!", "_not_"),
    ("+<", "_thru_"),
    ("+", "_ge_"), 
    ("<", "_lt_"),
    ("~", "_weak_"),
)


def safe_str(input_):

    for original, replacement in FILESYSTEM_CHARACTER_MAPPING:
        input_ = input_.replace(original, replacement)

    return input_
