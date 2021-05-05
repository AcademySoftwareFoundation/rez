name = 'soft'
version = '1'
authors = ['davidlatwe']
requires = [
    'soft_dep-1//harden(2)',
    'soft_lock_dep',
]
variants = [
    ['soft_var-2//harden(2)'],
    ['soft_var-3.*'],
]
build_command = False
