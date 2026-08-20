name = "late_binding_invalid"

version = "1.0"


@late()
def requires():
    # Returns a non-None value that will fail schema validation when a strict
    # schema is applied. Used to test the re-raise path in _wrap_forwarded.
    return 42


def commands() -> None:
    pass
