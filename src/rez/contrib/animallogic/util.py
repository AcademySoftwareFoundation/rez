
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

