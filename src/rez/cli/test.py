

def command(opts, parser=None):
    test_shells = False

    if (not opts.shells):
        # test all
        test_shells = True

    if opts.shells or test_shells:
        from rez.tests.shells import run
        run(opts.verbosity)
