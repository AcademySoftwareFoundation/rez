# **rez** with Rust 🦀

The `rust` directory contains source code for the portions of **rez** that
are written in the [**Rust**](https://www.rust-lang.org/) programming language.
Rust code is organized into [**crates**](https://doc.rust-lang.org/book/ch07-01-packages-and-crates.html), similar to Python packages.

| crate   | path       | description         |
| ------- | ---------- | ------------------- |
| **rez** | `rust/src` | core business logic |

**Rust code is entirely optional at the moment and provides no additional
functionality. However, it will likely provide performance improvements.**

## Building **rez** with Rust

- Clone [**rez**](https://github.com/nerdvegas/rez) from GitHub
- Install the [Rust toolchain](https://www.rust-lang.org/tools/install)
  - **rustc** - Rust compiler (1.58 or later)
  - **cargo** - Rust package manager
- Install [Python 3.7+](https://www.python.org/downloads/)

### Create a Python Virtual Environment

bash

```bash
python3 -m venv venv
source venv/bin/activate
```

pwsh

```powershell
py -3 -m venv venv
.\venv\Scripts\activate
```

### Install Python Dependencies

In your virtual environment install [Maturin](https://github.com/PyO3/maturin).
**Maturin** is a build tool used in combination with [PyO3](https://github.com/PyO3/pyo3)
to create bindings for Python calling into Rust code.

```bash
python -m pip install maturin
```

### Execute the Build

Build the crate with Python bindings and install it in the virtual environment.

```bash
maturin develop
```

You can see if it worked by running the following:

```bash
$ python -c "from rez import rez; rez.foo()"
Hello from Rust
```

For other Maturin commands check out their [docs](https://github.com/PyO3/maturin#usage).

## Important Files

- `rust/src/lib.rs` - the entrypoint file for **rez**'s Rust based code.
- `rust/.github` - GitHub Actions for building Rust code
- `Cargo.toml` - this is the equivalent of `pyproject.toml` or `setup.py` for a Rust crate.
- `Cargo.lock` - contains information about installed Rust crates. Should not be tracked in Git unless Rust code is exposed as an application rather than a library.

## Resources

- [PyO3](https://github.com/PyO3/pyo3) - Rust library that creates the Python bindings
- [Maturin](https://github.com/PyO3/maturin) - build tool Rust-Python bindings
