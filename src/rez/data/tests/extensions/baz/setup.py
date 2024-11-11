from __future__ import print_function, with_statement
from setuptools import setup, find_packages


setup(
    name="baz",
    version="0.1.0",
    package_dir={
        "baz": "baz"
    },
    packages=find_packages(where="."),
    entry_points={
        'rez.plugins': [
            'baz_cmd = baz',
        ]
    }
)
