
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


def filter_preferred_build_systems(valid_build_systems, preferred):

    build_systems = filter(lambda x : x.name() in preferred, valid_build_systems)

    return build_systems or valid_build_systems

