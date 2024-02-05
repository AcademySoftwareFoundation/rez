name = "winning"
version = "9.6"
description = (
    "Test cmake builds especially on Windows with Unix Makefiles generator. "
    "This is a handy workflow to have on Windows b/c it supports rez + cmake with "
    "minimal effort and w/o the overhead of Visual Studio. "
    "Note: Using cmake on Windows requires path normalization to be enabled. "
)

build_requires = [
    # make and cmake need to be installed locally for this test to build and succeed
]

def commands():
    env.PYTHONPATH.append("{root}/python")
