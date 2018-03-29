#!/usr/bin/python

import unittest

import common
from autotest_lib.site_utils.deployment import cmdparse


class ArgumentPairTestCase(unittest.TestCase):

    """Tests for parsing and adding argument pairs."""

    def test_missing_dest(self):
        """Test for error when missing dest argument."""
        parser = cmdparse._ArgumentParser()
        with self.assertRaisesRegexp(ValueError, r'\bdest\b'):
            parser.add_argument_pair('--yes', '--no', default=True)

    def test_missing_dest_and_default(self):
        """Test for error when missing dest and default arguments."""
        parser = cmdparse._ArgumentParser()
        with self.assertRaises(ValueError) as context:
            parser.add_argument_pair('--yes', '--no')
        message = str(context.exception)
        self.assertIn('dest', message)
        self.assertIn('default', message)

    def test_default_value(self):
        """Test the default value for an option pair."""
        parser = cmdparse._ArgumentParser()
        parser.add_argument_pair('--yes', '--no', dest='option',
                                 default=False)
        args = parser.parse_args([])
        self.assertIs(args.option, False)

    def test_parsing_flag(self):
        """Test parsing an option flag of an option pair."""
        parser = cmdparse._ArgumentParser()
        parser.add_argument_pair('--yes', '--no', dest='option',
                                 default=False)
        args = parser.parse_args(['--yes'])
        self.assertIs(args.option, True)

    def test_duplicate_flag_precedence(self):
        """Test precedence when passing multiple flags."""
        parser = cmdparse._ArgumentParser()
        parser.add_argument_pair('--yes', '--no', dest='option',
                                 default=False)
        args = parser.parse_args(['--no', '--yes'])
        self.assertIs(args.option, True)
        args = parser.parse_args(['--yes', '--no'])
        self.assertIs(args.option, False)


def _test_parse_command(argv, full_deploy):
    return cmdparse.parse_command(['command'] + argv, full_deploy)


class _CommandParserTestCase(unittest.TestCase):
    _ALL_FULL_DEPLOY_OPTIONS = [False, True]

    def _check_common_defaults(self, arguments):
        self.assertIsNone(arguments.web)
        self.assertIsNone(arguments.logdir)
        self.assertIsNone(arguments.build)
        self.assertIsNone(arguments.hostname_file)
        self.assertFalse(arguments.noinstall)
        self.assertFalse(arguments.nostage)
        self.assertFalse(arguments.nostable)
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
                self.assertTrue(arguments.noinstall)

    def test_nostage_option(self):
        """Test handling of `--nostage`, both long and short forms."""
        for option in ['-s', '--nostage']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option], full_deploy)
                self.assertTrue(arguments.nostage)

    def test_nostable_option(self):
        """Test handling of `--nostable`, both long and short forms."""
        for option in ['-t', '--nostable']:
            for full_deploy in self._ALL_FULL_DEPLOY_OPTIONS:
                arguments = _test_parse_command([option], full_deploy)
                self.assertTrue(arguments.nostable)

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
        self.assertTrue(arguments.full_deploy)

    def test_repair_test_defaults(self):
        """Test argument defaults for `repair_test`."""
        arguments = _test_parse_command([], False)
        self._check_common_defaults(arguments)
        self.assertFalse(arguments.upload)
        self.assertFalse(arguments.full_deploy)

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
