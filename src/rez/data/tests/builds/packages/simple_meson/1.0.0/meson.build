project(
  'simple',
  'c',
  meson_version : '>= 1.3.0',
  version : '1.0.0',
  default_options : ['warning_level=3'],
)

dependencies = [
]

exe = executable(
  'simple',
  'simple.c',
  dependencies : dependencies,
  install : true,
)

test('basic', exe)
