# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from setuptools import setup


setup(
    name="hello_cmd",
    version="1.0",
    package_dir={"hello_cmd": ""},
    packages=["hello_cmd",
              "hello_cmd.rezplugins",
              "hello_cmd.rezplugins.command"],
)
