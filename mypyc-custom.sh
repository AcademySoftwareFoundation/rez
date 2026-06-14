#!/bin/bash

set -e

#pip install ../mypy
pip uninstall -y rez
pip install --no-build-isolation -e .
python -m rez.cli._main selftest --debug
