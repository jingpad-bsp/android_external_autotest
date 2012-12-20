#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Infer and spawn a complete set of Chrome OS release autoupdate tests."""


import logging
import optparse
import os
import subprocess
import sys

import common
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.site_utils.autoupdate import board, release, test_image


# Global reference objects.
_board_info = board.BoardInfo()
_release_info = release.ReleaseInfo()


class FullReleaseTestError(BaseException):
  pass


class TestEnv(object):
    """Contains and formats the environment arguments of a test."""

    def __init__(self, args):
        """Initial environment arguments object.

        @param args: parsed program arguments, including test environment ones

        """
        self._env_args_str_local = None
        self._env_args_str_afe = None

        # Distill envionment arguments from all input arguments.
        self._env_args = []
        for key in ('servo_host', 'servo_port', 'omaha_host'):
            val = vars(args).get(key)
            if val is not None:
                self._env_args.append((key, val))


    def get_cmdline_args(self):
        """Return formatted environment arguments for command-line invocation.

        The formatted string is cached for repeated use.

        """
        if self._env_args_str_local is None:
            self._env_args_str_local = ''
            for key, val in self._env_args:
                # Convert Booleans to 'yes' / 'no'.
                if val is True:
                    val = 'yes'
                elif val is False:
                    val = 'no'

                self._env_args_str_local += ' %s=%s' % (key, val)

        return self._env_args_str_local


    def get_code_args(self):
        """Return formatted environment arguments for inline assignment.

        The formatted string is cached for repeated use.

        """
        if self._env_args_str_afe is None:
            self._env_args_str_afe = ''
            for key, val in self._env_args:
                # Everything becomes a string, except for Booleans.
                if type(val) is bool:
                    self._env_args_str_afe += "%s = %s\n" % (key, val)
                else:
                    self._env_args_str_afe += "%s = '%s'\n" % (key, val)

        return self._env_args_str_afe


class TestConfig(object):
    """A single test configuration.

    Stores and generates arguments for running autotest_EndToEndTest.

    """
    def __init__(self, board, name, mp_images, delta_update,
                 source_release, target_release, source_branch, target_branch,
                 source_image_uri, target_payload_uri):
        """Initialize a test configuration.

        @param board: the board being tested (e.g. 'x86-alex')
        @param name: a descriptive name of the test
        @param mp_images: whether or not we're using test images (Boolean)
        @param delta_update: whether this is a delta update test (Boolean)
        @param source_release: the source image version (e.g. '2672.0.0')
        @param target_release: the target image version (e.g. '2673.0.0')
        @param source_branch: the source release branch (e.g. 'R22')
        @param target_branch: the target release branch (e.g. 'R22')
        @param source_image_uri: source image URI ('gs://...')
        @param target_payload_uri: target payload URI ('gs://...')

        """
        self.board = board
        self.name = name
        self.mp_images = mp_images
        self.delta_update = delta_update
        self.source_release = source_release
        self.target_release = target_release
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.source_image_uri = source_image_uri
        self.target_payload_uri = target_payload_uri


    def get_image_type(self):
        return 'mp' if self.mp_images else 'test'


    def get_update_type(self):
        return 'delta' if self.delta_update else 'full'


    def __str__(self):
        """Short textual representation w/o image/payload URIs."""
        return ('[%s/%s/%s/%s/%s-%s -> %s-%s]' %
                (self.board, self.name, self.get_image_type(),
                 self.get_update_type(), self.source_branch,
                 self.source_release, self.target_branch, self.target_release))


    def __repr__(self):
        """Full textual representation w/ image/payload URIs."""
        return '\n'.join([str(self),
                          'source image   : %s' % self.source_image_uri,
                          'target payload : %s' % self.target_payload_uri])


    def _get_args(self, assign, delim, is_quote_val):
        template = "%s%s'%s'" if is_quote_val else "%s%s%s"
        return delim.join([template % (key, assign, val)
                           for key, val in [
                               ('board', self.board),
                               ('name', self.name),
                               ('image_type', self.get_image_type()),
                               ('update_type', self.get_update_type()),
                               ('source_release', self.source_release),
                               ('target_release', self.target_release),
                               ('source_branch', self.source_branch),
                               ('target_branch', self.target_branch),
                               ('source_image_uri', self.source_image_uri),
                               ('target_payload_uri',
                                self.target_payload_uri)]])

    def get_cmdline_args(self):
        return self._get_args('=', ' ', False)


    def get_code_args(self):
        args = self._get_args(' = ', '\n', True)
        return args + '\n' if args else ''


def get_release_branch(release):
    return _release_info.get_branch(release)


def generate_test_image_config(board, name, mp_images, delta_update,
                               source_release, target_release, payload_uri):
    """Constructs a single test config with given arguments.

    It'll automatically find and populate source/target branches as well as the
    source image URI.

    @param board: the board name on which the test executes (e.g. 'x86-alex')
    @param name: a descriptive name for the test
    @param mp_images: whether the test uses MP-signed images
    @param delta_update: whether we're testing a delta update
    @param source_release: the version of the source image (before update)
    @param target_release: the version of the target image (after update)
    @param payload_uri: URI of the update payload.

    """
    # Get branch tags.
    source_branch = get_release_branch(source_release)
    target_branch = get_release_branch(target_release)

    # Find the source image.
    source_image_uri = test_image.find_image_uri(board, source_release,
                                                 source_branch)
    # If found, return test configuration.
    if source_image_uri:
        return TestConfig(board, name, mp_images, delta_update, source_release,
                          target_release, source_branch, target_branch,
                          source_image_uri, payload_uri)
    else:
        logging.warning('cannot find source image for %s, %s', board,
                        source_release)


def generate_test_image_npo_nmo_list(board, tested_release, test_nmo,
                                     test_npo):
    """Generates N+1/N-1 test configurations with test images.

    Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
    given tested release and board. This is done by scanning of the test image
    repository, looking for update payloads; normally, we exppect to find at
    most one update payload of each of the aforementioned types.

    @param logging: a logging object
    @param board: the board under test
    @param tested_release: the tested release version
    @param test_nmo: whether we should infer N-1 tests
    @param test_npo: whether we should infer N+1 tests

    @return A list of TestConfig objects corresponding to the N+1 and N-1
            tests.

    @raise FullReleaseTestError if something went wrong

    """
    if not (test_nmo or test_npo):
        return []

    # Find all test delta payloads involving the release version at hand, then
    # figure out which is which.
    found = set()
    test_list = []
    payload_uri_list = test_image.find_payload_uri(
            board, tested_release, get_release_branch(tested_release),
            delta=True)
    for payload_uri in payload_uri_list:
        # Infer the source and target release versions.
        file_name = os.path.basename(payload_uri)
        source_release, target_release = (
                [version.split('-')[1]
                 for version in file_name.split('_')[1:3]])

        # With test images, the target release version is always the same as
        # the tested release (no upversioning performed for N+1).
        if target_release != tested_release:
            raise FullReleaseTestError(
                    'unexpected delta target release: %s != %s (%s)',
                    target_release, tested_release, board)

        # Determine delta type, make sure it was not already discovered.
        delta_type = 'npo' if source_release == target_release else 'nmo'
        if delta_type in found:
            raise FullReleaseTestError('more than one %s deltas found (%s, %s)',
                                       delta_type, board, tested_release)
        found.add(delta_type)

        # Generate test configuration.
        test_list.append(generate_test_image_config(
                board, delta_type, False, True, source_release, target_release,
                payload_uri))

    return test_list


def generate_mp_image_npo_nmo_list(board, tested_release, test_nmo, test_npo):
    """Generates N+1/N-1 test configurations with MP-signed images.

    Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
    given tested release and board.

    @param logging: a logging object
    @param board: the board under test
    @param tested_release: the tested release version
    @param test_nmo: whether we should infer N-1 tests
    @param test_npo: whether we should infer N+1 tests

    @return A pair of TestConfig objects corresponding to the N+1 and N-1
            tests.

    @raise FullReleaseTestError if something went wrong

    """
    # TODO(garnold) generate N+/-1 configurations for MP-signed images.
    raise NotImplementedError(
            'generation of mp-signed test configs not implemented')


def generate_npo_nmo_list(board, tested_release, mp_images, test_nmo,
                          test_npo):
    """Generates N+1/N-1 test configurations.

    Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
    given tested release and board.

    @param logging: a logging object
    @param board: the board under test
    @param tested_release: the tested release version
    @param mp_images: whether or not we're using MP-signed images
    @param test_nmo: whether we should infer N-1 tests
    @param test_npo: whether we should infer N+1 tests

    @return List of TestConfig objects corresponding to the requested test
            types.

    @raise FullReleaseTestError if something went wrong

    """
    # Return N+1/N-1 test configurations.
    if mp_images:
        return generate_mp_image_npo_nmo_list(board, tested_release, test_nmo,
                                              test_npo)
    else:
        return generate_test_image_npo_nmo_list(board, tested_release,
                                                test_nmo, test_npo)


def generate_test_image_fsi_list(board, tested_release):
    """Generates FSI test configurations with test images.

    Returns a list of test configurations from FSI releases to the given
    tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version

    @return List of TestConfig objects corresponding to the FSI tests for the
            given board.

    """
    test_list = []

    # First, find the full payload for the tested (target) release, since
    # we do not have delta payloads from FSIs.
    tested_payload_uri = test_image.find_payload_uri(
            board, tested_release, get_release_branch(tested_release),
            single=True)
    if not tested_payload_uri:
        logging.warning('cannot find full payload for %s, %s; no fsi tests',
                        board, tested_release)
        return []

    # Find as many FSI releases as are available, construct test list.
    fsi_releases = _board_info.get_fsi_releases(board)
    for fsi_source_release in fsi_releases:
        test_config = generate_test_image_config(
                board, 'fsi', False, False,
                fsi_source_release, tested_release, tested_payload_uri)
        if test_config:
            test_list.append(test_config)

    return test_list


def generate_mp_image_fsi_list(board, tested_release):
    """Generates FSI test configurations with MP-signed images.

    Returns a list of test configurations from FSI releases to the given
    tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version

    @return List of TestConfig objects corresponding to the FSI tests for the
            given board.

    """
    # TODO(garnold) configure FSI-to-N delta tests for MP-signed images.
    raise NotImplementedError(
        'generation of mp-signed test configs not implemented')


def generate_fsi_list(board, tested_release, mp_images):
    """Generates FSI test configurations.

    Returns a list of test configurations from FSI releases to the given
    tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version
    @param mp_images: whether or not we're using MP-signed images

    @return List of TestConfig objects corresponding to the FSI tests for the
            given board.

    """
    if mp_images:
        return generate_mp_image_fsi_list(board, tested_release)
    else:
        return generate_test_image_fsi_list(board, tested_release)


def generate_test_list(args):
    """Setup the test environment.

    @param args: execution arguments

    @return A list of test configurations.

    @raise FullReleaseTestError if anything went wrong.

    """
    # Initialize test list.
    test_list = []

    # Configure N-1-to-N and N-to-N+1 tests.
    if args.test_nmo or args.test_npo:
        test_list += generate_npo_nmo_list(
                args.tested_board, args.tested_release, args.mp_images,
                args.test_nmo, args.test_npo)

    # Configure FSI tests.
    if args.test_fsi:
        test_list += generate_fsi_list(
                args.tested_board, args.tested_release, args.mp_images)

    return test_list


def get_usage(argument_names):
    usage = 'Usage: %prog [options]'
    if argument_names:
        usage += ' ' + ' '.join(argument_names)
    return usage


def run_test_local(test, env, remote):
    """Run an end-to-end update test locally.

    @param test: the test configuration
    @param env: environment arguments for the test
    @param remote: remote DUT address

    """
    cmd = ['run_remote_tests.sh',
           '--args=%s%s' % (test.get_cmdline_args(), env.get_cmdline_args()),
           '--servo',
           '--remote=%s' % remote,
           '--allow_offline_remote',
           '--use_emerged',
           'autoupdate_EndToEndTest']
    logging.debug('executing: %s', ' '.join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError, e:
        raise FullReleaseTestError(
                'command execution failed: %s' % e)


def run_test_afe(test, env, control_code, afe_create_job_func):
    """Run an end-to-end update test via AFE.

    @param test: the test configuration
    @param env: environment arguments for the test
    @param control_code: content of the test control file
    @param afe_create_job: AFE function for creating test job

    @return The scheduled job ID.

    """
    # Parametrize the control script.
    parametrized_control_code = (
            test.get_code_args() + env.get_code_args() + control_code)

    # Create the job.
    job_id = afe_create_job_func(
            test.name, 'Medium', parametrized_control_code, 'Server',
            meta_hosts=['board:%s' % test.board], dependencies=['servo'])
    return job_id


def parse_args():
    argument_names = ('RELEASE', 'BOARD')

    desc = ('Schedule a set of update tests of Chrome OS version RELEASE for '
            'BOARD.')

    parser = optparse.OptionParser(usage=get_usage(argument_names),
                                   description=desc)

    parser.add_option('--nmo', dest='test_nmo', action='store_true',
                      help='generate N-1 update tests')
    parser.add_option('--npo', dest='test_npo', action='store_true',
                      help='generate N+1 update tests')
    parser.add_option('--fsi', dest='test_fsi', action='store_true',
                      help='generate FSI update tests')
    parser.add_option('--servo_host', metavar='ADDR', default='localhost',
                      help='host running servod (default: %default)')
    parser.add_option('--servo_port', metavar='PORT',
                      help='servod port (default: servod\'s default)')
    parser.add_option('--omaha_host', metavar='ADDR', default='localhost',
                      help='host where Omaha/devserver will be spawned '
                      '(default: %default)')
    parser.add_option('--mp_images', action='store_true',
                      help='use MP-signed images')
    parser.add_option('--remote', metavar='ADDR',
                      help='run test on given DUT via run_remote_tests')
    parser.add_option('--log', metavar='LEVEL', dest='log_level',
                      default='normal',
                      help='verbosity level: normal (default), verbose, debug')

    # Parse arguments.
    opts, args = parser.parse_args()

    # Get positional arguments, adding them as option values.
    if len(args) != len(argument_names):
        parser.error('unexpected number of arguments')
    opts.tested_release, opts.tested_board = args

    # Sanity check board.
    if opts.tested_board not in _board_info.get_board_names():
        parser.error('invalid board (%s)' % opts.tested_board)

    # Sanity check log level.
    if opts.log_level not in ('normal', 'verbose', 'debug'):
        parser.error('invalid log level (%s)' % opts.log_level)

    return opts


def main():
    try:
        # Initialize board/release configs.
        _board_info.initialize()
        _release_info.initialize()

        # Parse command-line arguments.
        args = parse_args()

        # Set log verbosity.
        if args.log_level == 'debug':
            logging.basicConfig(level=logging.DEBUG)
        elif args.log_level == 'verbose':
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.WARNING)

        # Create test configurations.
        test_list = generate_test_list(args)
        if not test_list:
            raise FullReleaseTestError(
                'no test configurations generated, nothing to do')

        # Construct environment argument, used for all tests.
        env = TestEnv(args)

        # Local or AFE invocation?
        if args.remote:
            # Running autoserv locally.
            for i, test in enumerate(test_list):
                logging.info('running test %d/%d:\n%r', i + 1, len(test_list),
                             test)
                run_test_local(test, env, args.remote)
        else:
            # Obtain the test control file content.
            control_file = os.path.join(
                    common.autotest_dir, 'server', 'site_tests',
                    'autoupdate_EndToEndTest', 'control')
            with open(control_file) as f:
                control_code = f.read()

            # Establish AFE RPC connection, obtain job creation RPC function.
            afe_proxy = rpc_client_lib.get_proxy(
                    'http://localhost/afe/server/noauth/rpc/')
            afe_create_job_func = getattr(afe_proxy, 'create_job')

            # Schedule jobs via AFE.
            for i, test in enumerate(test_list):
                logging.info('scheduling test %d/%d:\n%r', i + 1,
                             len(test_list), test)
                job_id = run_test_afe(test, env, control_code,
                                      afe_create_job_func)
                logging.info('job id: %s', job_id)

    except FullReleaseTestError, e:
        logging.fatal(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
