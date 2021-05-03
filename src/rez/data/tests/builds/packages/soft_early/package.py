name = 'soft_early'
version = '1'
authors = ['davidlatwe']


@early()
def requires():
    if building:
        return [
            'soft_dep-1//harden(2)',
            'soft_dep<1.1.0',
        ]
    else:
        return [
            'soft_dep-1',
        ]


variants = [
    ['soft_var-2//harden(2)'],
    ['soft_var-3.*'],
]
build_command = False
