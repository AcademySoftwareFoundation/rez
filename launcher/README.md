# Script launchers

This folder contains the script launchers. It is basically https://github.com/pypa/distlib/blob/0.3.7/PC/launcher.c
with some light modifications:

1. We don't embbed the scripts in the executable.
2. We removed the support to use environment variables to locate the interpreter.
3. We added a small patch to print the command executed if the environment variable
   REZ_LAUNCHER_DEBUG is set.

The launcher is only needed on Windows and is compiled from the setup.py file. MSVC
isn't required. We use the [Zig](https://ziglang.org) compiler (zig cc) to compile.

On Windows, native commands are wheel data under `.data/data/Scripts/rez`,
while `<command>-script.py` and `<command>-script.pyw` stay flat under `.data/scripts`. In a virtual environment
these become `<prefix>/Scripts/rez/<command>.exe` and
`<prefix>/Scripts/<command>-script.py` (or `.pyw` for GUI commands). The launcher
looks one directory up for `<command>-script.py(w)` and uses its installer-written shebang
to start the bound interpreter with `-E`.

Add only `Scripts/rez` to `PATH`, not the parent directory containing Python.
