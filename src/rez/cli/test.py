'''
Run unit tests
'''

def setup_parser(parser):
    parser.add_argument("--shells", action="store_true",
                        help="test shell invocation")
    parser.add_argument("-v", "--verbosity", type=int, default=2,
                        help="set verbosity level")

def command(opts, parser=None):
    test_shells = False

    if (not opts.shells):
        # test all
        test_shells = True

    if opts.shells or test_shells:
        from rez.tests.shells import run
        run(opts.verbosity)
