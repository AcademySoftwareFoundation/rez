#!/bin/bash

set -e

builddir=./build

rm -rf $builddir
_REZ_NO_KILLPG=1 python ./install.py -v $builddir


#$builddir/bin/rez/rez-selftest

#_REZ_NO_KILLPG=1 ./build/bin/python -c "import rez.utils.resources; print(rez.utils.resources.__file__); "
#_REZ_NO_KILLPG=1 ./build/bin/python -c "import rez.solver; print(rez.solver.__file__)"
#_REZ_NO_KILLPG=1 ./build/bin/python -c "import rez.resolver; print(rez.resolver.__file__)"
#_REZ_NO_KILLPG=1 ./build/bin/python -c "import rez.packages; print(rez.packages.__file__)"
# ./build/bin/python -c "import rez.version._version; print(rez.version._version.__file__)"

./build/bin/rez/rez-selftest

# ./build/bin/rez/rez-benchmark --out ./out-solver-resolver

# PYTHONPATH=src python -c "import rez.utils.data_utils;rez.utils.data_utils.write_all_dynamic_members()"

# python -m rez.cli._main selftest