# Build instructions

To build the docs you must install the following requirements:

- GNU Make (Linux + Mac only)
- Python 3.11

To create a build environment run the following commands:
```python
python -m venv .venv
source .venv/bin/activate
pip install -r docs/requirements.txt

cd docs
make html # .\make html on Windows
```

# Example Headers

============
page section
============

Section 1
=========

Section 1.1
-----------

Section 1.1.1
+++++++++++++

Section 1.1.1.1
***************
