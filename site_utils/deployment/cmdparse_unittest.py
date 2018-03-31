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


def _test_parse_deprecated_command(argv, full_deploy):
    return cmdparse.parse_deprecated_command(
        ['command'] + argv, full_deploy)


def _test_parse_command(argv):
    return cmdparse.parse_command(['command'] + argv)


class _CommandParserTestCase(unittest.TestCase):
    _ALL_FULL_DEPLOY_OPTIONS = [False, True]
    _ALL_SUBCOMMANDS = ['servo', 'firmware', 'test-image', 'repair']

    def _check_common_defaults(self, arguments):
        self.assertIsNone(arguments.web)
        self.assertIsNone(arguments.logdir)
        self.assertFalse(arguments.dry_run)
        self.assertIsNone(arguments.board)
        self.assertIsNone(arguments.build)
        self.assertIsNone(arguments.hostname_file)
        self.assertEquals(arguments.hostnames, [])

    def test_web_option(self):
        """Test handling of `--web`, both long and short forms."""
        opt_arg = 'servername'
        for option in ['-w', '--web']:
            argv = [option, opt_arg]
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(argv, full_deploy)
                self.assertEquals(arguments.web, opt_arg)
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd] + argv)
                self.assertEquals(arguments.web, opt_arg)

    def test_logdir_option(self):
        """Test handling of `--dir`, both long and short forms."""
        opt_arg = 'dirname'
        for option in ['-d', '--dir']:
            argv = [option, opt_arg]
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(argv, full_deploy)
                self.assertEquals(arguments.logdir, opt_arg)
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd] + argv)
                self.assertEquals(arguments.logdir, opt_arg)

    def test_dry_run_option(self):
        """Test handling of `--dry-run`, both long and short forms."""
        # assert False
        for option in ['-n', '--dry-run']:
            argv = [option]
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(argv, full_deploy)
                self.assertTrue(arguments.dry_run)
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd] + argv)
                self.assertTrue(arguments.dry_run)

    def test_build_option(self):
        """Test handling of `--build`, both long and short forms."""
        opt_arg = 'R66-10447.0.0'
        for option in ['-i', '--build']:
            argv = [option, opt_arg]
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(argv, full_deploy)
                self.assertEquals(arguments.build, opt_arg)
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd] + argv)
                self.assertEquals(arguments.build, opt_arg)

    def test_hostname_file_option(self):
        """Test handling of `--hostname_file`, both long and short forms."""
        opt_arg = 'hostfiles.csv'
        for option in ['-f', '--hostname_file']:
            argv = [option, opt_arg]
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(argv, full_deploy)
                self.assertEquals(arguments.hostname_file, opt_arg)
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd] + argv)
                self.assertEquals(arguments.hostname_file, opt_arg)

    def test_nostage_option(self):
        """Test handling of `--nostage`, both long and short forms."""
        for option in ['-s', '--nostage']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_deprecated_command(
                        [option], full_deploy)
                self.assertFalse(arguments.stageusb)

    def test_upload_option(self):
        """Test handling of `--upload`, both long and short forms."""
        argv = ['--upload']
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_deprecated_command(argv, full_deploy)
            self.assertTrue(arguments.upload)
        for subcmd in self._ALL_SUBCOMMANDS:
            arguments = _test_parse_command([subcmd] + argv)
            self.assertTrue(arguments.upload)

    def test_noupload_option(self):
        """Test handling of `--noupload`, both long and short forms."""
        argv = ['--noupload']
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_deprecated_command(argv, full_deploy)
            self.assertFalse(arguments.upload)
        for subcmd in self._ALL_SUBCOMMANDS:
            arguments = _test_parse_command([subcmd] + argv)
            self.assertFalse(arguments.upload)

    def _check_deprecated_defaults(self, arguments):
        self._check_common_defaults(arguments)
        self.assertTrue(arguments.stageusb)
        self.assertTrue(arguments.install_test_image)

    def test_deprecated_deployment_test_defaults(self):
        """Test argument defaults for `deployment_test`."""
        arguments = _test_parse_deprecated_command([], True)
        self._check_deprecated_defaults(arguments)
        self.assertTrue(arguments.upload)
        self.assertTrue(arguments.install_firmware)

    def test_deprecated_repair_test_defaults(self):
        """Test argument defaults for `repair_test`."""
        arguments = _test_parse_deprecated_command([], False)
        self._check_deprecated_defaults(arguments)
        self.assertFalse(arguments.upload)
        self.assertFalse(arguments.install_firmware)

    def test_deprecated_board_no_hostnames(self):
        """Test handling when a board is supplied without hostnames."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_deprecated_command(
                    ['board1'], full_deploy)
            self.assertEquals(arguments.board, 'board1')
            self.assertEquals(arguments.hostnames, [])

    def test_deprecated_board_and_hostname_arguments(self):
        """Test handling when both board and hostnames are supplied."""
        for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
            arguments = _test_parse_deprecated_command(
                    ['board1', 'host1'], full_deploy)
            self.assertEquals(arguments.board, 'board1')
            self.assertEquals(arguments.hostnames, ['host1'])

    def test_board_option(self):
        """Test the `--board` option for subcommands."""
        opt_arg = 'board'
        for option in ['-b', '--board']:
            for subcmd in self._ALL_SUBCOMMANDS:
                arguments = _test_parse_command([subcmd, option, opt_arg])
                self.assertEquals(arguments.board, opt_arg)

    def test_hostname_arguments(self):
        """Test hostname arguments for subcommands."""
        argument = 'hostname'
        for subcmd in self._ALL_SUBCOMMANDS:
            arguments = _test_parse_command([subcmd, argument])
            self.assertEquals(arguments.hostnames, [argument])

    def test_servo_defaults(self):
        """Test argument defaults for `deploy servo`."""
        arguments = _test_parse_command(['servo'])
        self._check_common_defaults(arguments)
        self.assertTrue(arguments.stageusb)
        self.assertFalse(arguments.install_firmware)
        self.assertFalse(arguments.install_test_image)

    def test_firmware_defaults(self):
        """Test argument defaults for `deploy firmware`."""
        arguments = _test_parse_command(['firmware'])
        self._check_common_defaults(arguments)
        self.assertFalse(arguments.stageusb)
        self.assertTrue(arguments.install_firmware)
        self.assertTrue(arguments.install_test_image)

    def test_test_image_defaults(self):
        """Test argument defaults for `deploy test-image`."""
        arguments = _test_parse_command(['test-image'])
        self._check_common_defaults(arguments)
        self.assertFalse(arguments.stageusb)
        self.assertFalse(arguments.install_firmware)
        self.assertTrue(arguments.install_test_image)

    def test_repair_defaults(self):
        """Test argument defaults for `deploy repair`."""
        arguments = _test_parse_command(['repair'])
        self._check_common_defaults(arguments)
        self.assertFalse(arguments.stageusb)
        self.assertFalse(arguments.install_firmware)
        self.assertTrue(arguments.install_test_image)


if __name__ == '__main__':
    unittest.main()
