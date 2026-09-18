project(
  'advanced',
  'cpp',
  meson_version: '>= 1.3.0',
  version: '1.0.0',
  default_options: ['warning_level=3'],
)

exe = executable(
  'say',
  'main.cpp',
  dependencies: dependency('hello'),
  install: true,
)

test('basic', exe)
