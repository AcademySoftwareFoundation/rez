name = 'usdBase'
version = '0.8.al3.1.0'
description = 'universal scene description'
private_build_requires = ['cmake-2.8',
                        'gcc-4.8',
                        'gdb',
                        ]
requires = ['stdlib-4.8',
            'tbb-4.4',
            'ilmbase-2.2',
            ]

variants = [[ 'AL_boost-1.55.0', 'AL_boost_python-1.55'],
['boost-1.55.0', 'boost_python-1.55']]

use_chroot = True

def commands():
    prependenv('PATH', '{root}/bin')
    prependenv('PYTHONPATH', '{root}/lib/python')
    prependenv('LD_LIBRARY_PATH', '{root}/lib')
