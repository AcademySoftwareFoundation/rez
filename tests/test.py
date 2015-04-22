"""Enables unit testing from root directory of source."""
import os.path
import inspect


def load_tests(loader, standard_tests, pattern):
    root_test_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
    src_dir = os.path.join(root_test_dir, '..', 'src')
    src_test_dir = os.path.join(src_dir, 'rez', 'tests')

    if not pattern:
        pattern = 'test_*.py'
    suite = loader.discover(src_test_dir, pattern=pattern,
                            top_level_dir=src_dir)
    if standard_tests:
        suite.addTests(standard_tests)
    return suite
