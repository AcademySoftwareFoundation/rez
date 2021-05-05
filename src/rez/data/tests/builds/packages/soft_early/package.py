name = 'soft_early'
version = '1'
authors = ['davidlatwe']


@early()
def requires():
    if building:
        return [
            'soft_dep-1//harden(2)',
            'soft_lock_dep',
        ]
    else:
        return [
            'soft_dep-1//harden(2)',
        ]


build_command = False
