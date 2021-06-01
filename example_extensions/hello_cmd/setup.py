from __future__ import print_function, with_statement
from setuptools import setup


setup(
    name="hello_cmd",
    version="1.0",
    package_dir={"hello_cmd": ""},
    packages=["hello_cmd",
              "hello_cmd.rezplugins",
              "hello_cmd.rezplugins.command"],
)
