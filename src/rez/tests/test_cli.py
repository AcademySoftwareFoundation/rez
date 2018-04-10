"""
test configuration settings
"""
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, get_cli_output

import os.path

class TestConfig(TestBase, TempdirMixin):

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.settings = {}

    def test_1_logfile(self):
        from rez import __version__

        logfile_cli = os.path.join(self.root, 'rez_logfile_cli.txt')
        logfile_cfg = os.path.join(self.root, 'rez_logfile_cfg.txt')
        logfile_cfg2 = os.path.join(self.root, 'rez_logfile_cfg2.txt')
        def _do_logfile_test(args, expected, returncode=0, add_arg=True,
                             logfile=logfile_cli):
            if add_arg:
                args += ['--logfile', logfile]
            output, actual_returncode = get_cli_output(args)
            self.assertEqual(actual_returncode, returncode)
            self.assertEqual(output.strip(), expected)
            with open(logfile, 'r') as f:
                log_output = f.read()
            self.assertEqual(log_output.strip(), expected)


        # assert that if we don't specify --logfile, no logfile is made...
        self.assertFalse(os.path.isfile(logfile_cli))
        get_cli_output(['config'])
        self.assertFalse(os.path.isfile(logfile_cli))

        # now check that if we specify logfile, it exists, with expected
        # content
        status_expected = '''Using Rez v%s

No active context.

No visible suites.''' % __version__
        _do_logfile_test(['status'], status_expected)

        # make sure it works with stderr..
        context_expected = 'not in a resolved environment context.'
        _do_logfile_test(['context'], context_expected, returncode=1)

        # now check that logfile is made if we specify it through config
        self.update_settings({'logfile': logfile_cfg})
        os.remove(logfile_cli)
        self.assertFalse(os.path.isfile(logfile_cfg))
        _do_logfile_test(['status'], status_expected, add_arg=False,
                         logfile=logfile_cfg)
        self.assertFalse(os.path.isfile(logfile_cli))

        # now check that the cli logfile overrides the config
        os.remove(logfile_cfg)
        _do_logfile_test(['context'], context_expected, returncode=1)
        self.assertFalse(os.path.isfile(logfile_cfg))

        # now check that the logfile_by_command overrides the global config
        # logfile...
        self.update_settings({'logfile': logfile_cfg,
                              'logfile_by_command': {'status': logfile_cfg2}})
        os.remove(logfile_cli)
        self.assertFalse(os.path.isfile(logfile_cli))
        self.assertFalse(os.path.isfile(logfile_cfg2))
        _do_logfile_test(['status'], status_expected, add_arg=False,
                         logfile=logfile_cfg2)
        self.assertFalse(os.path.isfile(logfile_cli))
        self.assertFalse(os.path.isfile(logfile_cfg))

        #...but that it doesn't override if not using the right command...
        os.remove(logfile_cfg2)
        _do_logfile_test(['context'], context_expected, returncode=1,
                         add_arg=False, logfile=logfile_cfg)
        self.assertFalse(os.path.isfile(logfile_cli))
        self.assertFalse(os.path.isfile(logfile_cfg2))

        # check to make sure logfile_by_command is still overridden by
        # commandline
        os.remove(logfile_cfg)
        _do_logfile_test(['status'], status_expected)
        self.assertFalse(os.path.isfile(logfile_cfg))
        self.assertFalse(os.path.isfile(logfile_cfg2))

        # finally, make sure EVERYTHING is overridden by --no-logfile
        os.remove(logfile_cli)
        output, exitcode = get_cli_output(['status', '--no-logfile',
                                           '--logfile', logfile_cli])
        self.assertEqual(output.strip(), status_expected)
        self.assertEqual(exitcode, 0)
        self.assertFalse(os.path.isfile(logfile_cli))
        self.assertFalse(os.path.isfile(logfile_cfg))
        self.assertFalse(os.path.isfile(logfile_cfg2))