import rez.contrib.unittest2 as unittest



def command(opts, parser=None):
    suites = []
    test_all = \
        (not opts.shells) and \
        (not opts.versions)

    if opts.shells or test_all:
        from rez.tests.shells import get_test_suites
        suites += get_test_suites()

    if opts.versions or test_all:
        from rez.tests.versions import get_test_suites
        suites += get_test_suites()

    all_ = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=opts.verbosity).run(all_)
