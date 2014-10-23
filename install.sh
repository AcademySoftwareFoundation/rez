# Install script required to get the right environment for CMake to run the 
# setup.py install step.  Lame.

mkdir -p @python_library_dir@

PYTHONPATH=@python_library_dir@:$PYTHONPATH $PYTHON_EXE setup.py install --prefix=@CMAKE_INSTALL_PREFIX@

