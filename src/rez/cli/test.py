from rez.settings import settings
import unittest
import threading
import sys



def get_suites(opts, threaded=False):
    suites = []
    test_all = \
        (not opts.shells) and \
        (not opts.solver) and \
        (not opts.cli) and \
        (not opts.formatter) and \
        (not opts.commands) and \
        (not opts.rex) and \
        (not opts.build)

    if opts.shells or test_all:
        from rez.tests.shells import get_test_suites
        suites += get_test_suites()

    if opts.solver or test_all:
        from rez.tests.solver import get_test_suites
        suites += get_test_suites()

    if opts.cli or test_all:
        from rez.tests.cli import get_test_suites
        suites += get_test_suites()

    if opts.formatter or test_all:
        from rez.tests.formatter import get_test_suites
        suites += get_test_suites()

    if opts.commands or test_all:
        from rez.tests.commands import get_test_suites
        suites += get_test_suites()

    if opts.rex or test_all:
        from rez.tests.rex import get_test_suites
        suites += get_test_suites()

    # the build test isn't amenable to threaded testing - there's class-level
    # setup, and the package builds would trample over each other
    if not threaded and (opts.build or test_all):
        from rez.tests.build import get_test_suites
        suites += get_test_suites()

    return suites


def command(opts, parser=None):
    # test for thread safety
    if opts.thread:
        nthreads = 4
        threads = []

        def fn(runner, test_suite):
            result = runner.run(test_suite)
            if not result.wasSuccessful():
                sys.exit(1)

        for i in range(nthreads):
            suites = get_suites(opts, threaded=True)
            test_suite = unittest.TestSuite(suites)
            runner = unittest.TextTestRunner(verbosity=opts.verbosity)
            th = threading.Thread(target=fn, args=(runner, test_suite))
            th.setDaemon(True)
            threads.append(th)

        for th in threads:
            th.start()

        for th in threads:
            th.join()

    # run tests non-threaded
    suites = get_suites(opts)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbosity).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
