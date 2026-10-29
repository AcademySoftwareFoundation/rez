name = "late_binding_none"

version = "1.0"


@late()
def requires():
    pass


@late()
def build_requires():
    pass


@late()
def private_build_requires():
    pass


def commands() -> None:
    pass
