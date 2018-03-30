#!/usr/bin/python

import contextlib
import sys
import unittest

import common
from autotest_lib.site_utils.deployment import cmdparse


@contextlib.contextmanager
def _suppress_error_output():
    stderr_save = sys.stderr
    try:
        with open('/dev/null', 'w') as sys.stderr:
            yield
    finally:
        sys.stderr = stderr_save


class BooleanArgumentTestCase(unittest.TestCase):
    """Tests for parsing and adding boolean arguments."""

    def _make_parser(self, option, default):
        parser = cmdparse._ArgumentParser()
        parser.add_boolean_argument(option, default)
        return parser

    def test_conflicting_options_raises_error_with_false_default(self):
        """Test handling when both the true and false options are used."""
        # By default, when there's a command line syntax error,
        # `argparse.ArgumentParser` prints messages on sys.stderr and
        # then calls `sys.exit()`.  So, take the time to catch/suppress
        # those behaviors.
        with _suppress_error_output():
            parser = self._make_parser('option', False)
            with self.assertRaises(SystemExit):
                parser.parse_args(['--option', '--nooption'])
            with self.assertRaises(SystemExit):
                parser.parse_args(['--nooption', '--option'])

    def test_conflicting_options_raises_error_with_true_default(self):
        """Test handling when both the true and false options are used."""
        # By default, when there's a command line syntax error,
        # `argparse.ArgumentParser` prints messages on sys.stderr and
        # then calls `sys.exit()`.  So, take the time to catch/suppress
        # those behaviors.
        with _suppress_error_output():
            parser = self._make_parser('option', True)
            with self.assertRaises(SystemExit):
                parser.parse_args(['--option', '--nooption'])
            with self.assertRaises(SystemExit):
                parser.parse_args(['--nooption', '--option'])

    def test_no_option_wth_false_default(self):
        """Test option handling when no option is provided."""
        parser = self._make_parser('option', False)
        arguments = parser.parse_args([])
        self.assertFalse(arguments.option)

    def test_no_option_wth_true_default(self):
        """Test option handling when no option is provided."""
        parser = self._make_parser('option', True)
        arguments = parser.parse_args([])
        self.assertTrue(arguments.option)

    def test_true_option_returns_true_with_false_default(self):
        """Test option handling when only the true option is provided."""
        parser = self._make_parser('option', False)
        arguments = parser.parse_args(['--option'])
        self.assertTrue(arguments.option)

    def test_true_option_returns_true_with_true_default(self):
        """Test option handling when only the true option is provided."""
        parser = self._make_parser('option', True)
        arguments = parser.parse_args(['--option'])
        self.assertTrue(arguments.option)

    def test_false_option_returns_false_with_false_default(self):
        """Test option handling when only the false option is provided."""
        parser = self._make_parser('option', False)
        arguments = parser.parse_args(['--nooption'])
        self.assertFalse(arguments.option)

    def test_false_option_returns_false_with_true_default(self):
        """Test option handling when only the false option is provided."""
        parser = self._make_parser('option', True)
        arguments = parser.parse_args(['--nooption'])
        self.assertFalse(arguments.option)


def _test_parse_command(argv, full_deploy):
    return cmdparse.parse_command(['command'] + argv, full_deploy)


class _CommandParserTestCase(unittest.TestCase):
    _ALL_FULL_DEPLOY_OPTIONS = [False, True]

    def _check_common_defaults(self, arguments):
        self.assertIsNone(arguments.web)
        self.assertIsNone(arguments.logdir)
        self.assertIsNone(arguments.build)
        self.assertIsNone(arguments.hostname_file)
        self.assertTrue(arguments.stageusb)
        self.assertTrue(arguments.install_test_image)
        self.assertTrue(arguments.assign_repair_image)
        self.assertIsNone(arguments.board)
        self.assertEquals(arguments.hostnames, [])

    def test_web_option(self):
        """Test handling of `--web`, both long and short forms."""
        opt_arg = 'servername'
        for option in ['-w', '--web']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option, opt_arg], full_deploy)
                self.assertEquals(arguments.web, opt_arg)

    def test_logdir_option(self):
        """Test handling of `--dir`, both long and short forms."""
        opt_arg = 'dirname'
        for option in ['-d', '--dir']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option, opt_arg], full_deploy)
                self.assertEquals(arguments.logdir, opt_arg)

    def test_build_option(self):
        """Test handling of `--build`, both long and short forms."""
        opt_arg = 'R66-10447.0.0'
        for option in ['-i', '--build']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option, opt_arg], full_deploy)
                self.assertEquals(arguments.build, opt_arg)

    def test_hostname_file_option(self):
        """Test handling of `--hostname_file`, both long and short forms."""
        opt_arg = 'hostfiles.csv'
        for option in ['-f', '--hostname_file']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option, opt_arg], full_deploy)
                self.assertEquals(arguments.hostname_file, opt_arg)

    def test_noinstall_option(self):
        """Test handling of `--noinstall`, both long and short forms."""
        for option in ['-n', '--noinstall']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option], full_deploy)
                self.assertFalse(arguments.install_test_image)

    def test_nostage_option(self):
        """Test handling of `--nostage`, both long and short forms."""
        for option in ['-s', '--nostage']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option], full_deploy)
                self.assertFalse(arguments.stageusb)

    def test_nostable_option(self):
        """Test handling of `--nostable`, both long and short forms."""
        for option in ['-t', '--nostable']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option], full_deploy)
                self.assertFalse(arguments.assign_repair_image)

    def test_upload_option(self):
        """Test handling of `--upload`, both long and short forms."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_command(['--upload'], full_deploy)
            self.assertTrue(arguments.upload)

    def test_noupload_option(self):
        """Test handling of `--noupload`, both long and short forms."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_command(['--noupload'], full_deploy)
            self.assertFalse(arguments.upload)

    def test_deployment_test_defaults(self):
        """Test argument defaults for `deployment_test`."""
        arguments = _test_parse_command([], True)
        self._check_common_defaults(arguments)
        self.assertTrue(arguments.upload)
        self.assertTrue(arguments.install_firmware)

    def test_repair_test_defaults(self):
        """Test argument defaults for `repair_test`."""
        arguments = _test_parse_command([], False)
        self._check_common_defaults(arguments)
        self.assertFalse(arguments.upload)
        self.assertFalse(arguments.install_firmware)

    def test_board_no_hostnames(self):
        """Test handling when a board is supplied without hostnames."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_command(['board1'], full_deploy)
            self.assertEquals(arguments.board, 'board1')
            self.assertEquals(arguments.hostnames, [])

    def test_board_and_hostname_arguments(self):
        """Test handling when both board and hostnames are supplied."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_command(
                    ['board1', 'host1'], full_deploy)
            self.assertEquals(arguments.board, 'board1')
            self.assertEquals(arguments.hostnames, ['host1'])


if __name__ == '__main__':
    unittest.main()
