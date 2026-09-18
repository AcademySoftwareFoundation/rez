project(
  'hello',
  'cpp',
  meson_version: '>= 1.3.0',
  version: '1.1.0',
  default_options: ['warning_level=3'],
)

lib = library(
  'hello',
  'hello.cpp',
  install: true,
)

install_headers(
  'hello.hpp',
  subdir: 'hello',
)

pkg = import('pkgconfig')
pkg.generate(lib)
