import datetime


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


def get_epoch_datetime_from_str(s, format_="%Y-%m-%d %H:%M:%S"):

    from rez.utils.formatting import get_epoch_time_from_str

    try:
        # First try and get the time from rez.util, which assumes either the 
        # value of s is an int, or a relative time such as -1d.
        epoch = get_epoch_time_from_str(s)
        return datetime.datetime.fromtimestamp(epoch)
    except ValueError, e:
        # If that doesn't work, try and parse the time based on a particular 
        #format.
        return datetime.datetime.strptime(s, format_)

    raise ValueError("'%s' is an unrecognised time format." % s)
