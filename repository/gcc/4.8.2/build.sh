#!/usr/bin/bash

build_dir=$1
install_dir=$2
archive_dir=$3
gcc_ver=$4
gmp_ver=$5
mpfr_ver=$6
mpc_ver=$7

cd ${build_dir}

if [ ! -d gcc-${gcc_ver} ]; then
    archive=${archive_dir}/gcc/gcc-${gcc_ver}.tar.bz2
    echo "Extracting gcc from ${archive}..."
    tar xjf ${archive}
fi

# equivalent to gcc's 'download_prerequisites' script, but doesn't wget
cd gcc-${gcc_ver}
echo "Extracting prerequisites..."
if [ ! -L gmp ]; then
    echo "gmp..."
    tar xjf ${archive_dir}/gcc/gmp-${gmp_ver}.tar.bz2
    ln -s gmp-${gmp_ver} gmp

    # weirdly, without the following fix we sometimes get the following error while
    # running make, but only if in rez-env shell (even after patching up the env so
    # it's identical to the pre-rez-env shell, which is really odd):
    #
    # checking for flex... flex
    # checking lex output file root... configure: error: cannot find output from flex; giving up
    #
    # in the log left in gmp/config.log we see:
    # flex conftest.l
    # flex: fatal internal error, exec failed
    #
    # https://gmplib.org/list-archives/gmp-bugs/2010-December/002131.html
    # and the fix: https://gmplib.org/list-archives/gmp-bugs/2010-December/002132.html
    sed -e 's/M4=m4-not-needed/: # &/' -i gmp/configure
fi

if [ ! -L mpfr ]; then
    echo "mpfr..."
    tar xjf ${archive_dir}/gcc/mpfr-${mpfr_ver}.tar.bz2
    ln -s mpfr-${mpfr_ver} mpfr
fi

if [ ! -L mpc ]; then
    echo "mpc..."
    tar xzf ${archive_dir}/gcc/mpc-${mpc_ver}.tar.gz
    ln -s mpc-${mpc_ver} mpc
fi

# configure
cd ..
if [ -d objdir ]; then
    cd objdir
else
    mkdir objdir
    cd objdir
    ../gcc-${gcc_ver}/configure --prefix=${install_dir} --build=x86_64-linux-gnu --host=x86_64-linux-gnu --target=x86_64-linux-gnu --enable-languages=c,c++ --with-pic --enable-shared --enable-static --enable-threads=posix --enable-__cxa_atexit --enable-clocale=gnu --with-libelf=/usr/include --disable-multilib --disable-bootstrap --disable-install-libiberty --with-system-zlib --enable-linker-build-id --without-included-gettext --enable-nls --enable-clocale=gnu --enable-libstdcxx-debug --enable-libstdcxx-time=yes --enable-gnu-unique-object --enable-plugin --disable-werror --with-arch-32=i686 --with-tune=generic --enable-checking=release

fi

# build
make -j${REZ_BUILD_THREAD_COUNT}
