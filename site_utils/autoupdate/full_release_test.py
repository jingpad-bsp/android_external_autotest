#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Infer and spawn a complete set of Chrome OS release autoupdate tests.

By default, this runs against the AFE configured in the global_config.ini->
SERVER->hostname. You can run this on a local AFE by modifying this value in
your shadow_config.ini to localhost.
"""


import logging
import optparse
import os
import subprocess
import sys

import common
from autotest_lib.server import frontend
from autotest_lib.site_utils.autoupdate import board, release, test_image


# Global reference objects.
_board_info = board.BoardInfo()
_release_info = release.ReleaseInfo()

_log_debug = 'debug'
_log_normal = 'normal'
_log_verbose = 'verbose'
_valid_log_levels = _log_debug, _log_normal, _log_verbose
_autotest_url_format = r'http://%(host)s/afe/#tab_id=view_job&object_id=%(job)s'
_autotest_test_name = 'autoupdate_EndToEndTest'


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

        # Distill environment arguments from all input arguments.
        self._env_args = {}
        for key in ('servo_host', 'servo_port', 'omaha_host'):
            val = vars(args).get(key)
            if val is not None:
                self._env_args[key] = val


    def is_var_set(self, var):
        """Returns true if the |var| is set in this environment."""
        return var in self._env_args


    def get_cmdline_args(self):
        """Return formatted environment arguments for command-line invocation.

        The formatted string is cached for repeated use.

        """
        if self._env_args_str_local is None:
            self._env_args_str_local = ''
            for key, val in self._env_args.iteritems():
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
            for key, val in self._env_args.iteritems():
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
    def __init__(self, board, name, use_mp_images, is_delta_update,
                 source_release, target_release, source_branch, target_branch,
                 source_image_uri, target_payload_uri):
        """Initialize a test configuration.

        @param board: the board being tested (e.g. 'x86-alex')
        @param name: a descriptive name of the test
        @param use_mp_images: whether or not we're using test images (Boolean)
        @param is_delta_update: whether this is a delta update test (Boolean)
        @param source_release: the source image version (e.g. '2672.0.0')
        @param target_release: the target image version (e.g. '2673.0.0')
        @param source_branch: the source release branch (e.g. 'R22')
        @param target_branch: the target release branch (e.g. 'R22')
        @param source_image_uri: source image URI ('gs://...')
        @param target_payload_uri: target payload URI ('gs://...')

        """
        self.board = board
        self.name = name
        self.use_mp_images = use_mp_images
        self.is_delta_update = is_delta_update
        self.source_release = source_release
        self.target_release = target_release
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.source_image_uri = source_image_uri
        self.target_payload_uri = target_payload_uri


    def get_image_type(self):
        return 'mp' if self.use_mp_images else 'test'


    def get_update_type(self):
        return 'delta' if self.is_delta_update else 'full'


    def get_autotest_name(self):
        # Conforms to suite naming style assuming autoupdate is the suite name.
        return '%s-release/%s-%s/au/%s.%s_%s-%s' % (
                self.board, self.target_branch, self.target_release,
                _autotest_test_name, self.name, self.source_branch,
                self.source_release,)


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


def generate_mp_image_specific_list(board, tested_release,
                                    specific_source_releases):
    """Generates specific test configurations with MP-signed images.

    Returns a list of test configurations from a given list of source releases
    to the given tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version
    @param specific_source_releases: list of source releases to test

    @return List of TestConfig objects corresponding to the given source
            releases.

    """
    # TODO(garnold) configure FSI-to-N delta tests for MP-signed images.
    raise NotImplementedError(
        'generation of mp-signed test configs not implemented')


def generate_test_image_config(board, name, use_mp_images, is_delta_update,
                               source_release, target_release, payload_uri,
                               src_as_payload):
    """Constructs a single test config with given arguments.

    It'll automatically find and populate source/target branches as well as the
    source image URI.

    @param board: the board name on which the test executes (e.g. 'x86-alex')
    @param name: a descriptive name for the test
    @param use_mp_images: whether the test uses MP-signed images
    @param is_delta_update: whether we're testing a delta update
    @param source_release: the version of the source image (before update)
    @param target_release: the version of the target image (after update)
    @param payload_uri: URI of the update payload.
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).
    """
    # Get branch tags.
    source_branch = get_release_branch(source_release)
    target_branch = get_release_branch(target_release)

    # Find the source image.
    if src_as_payload:
        source_image_uri = test_image.find_payload_uri(board, source_release,
                                                       source_branch,
                                                       single=True)
    else:
        source_image_uri = test_image.find_image_uri(board, source_release,
                                                     source_branch)
    # If found, return test configuration.
    if source_image_uri:
        return TestConfig(board, name, use_mp_images, is_delta_update,
                          source_release, target_release, source_branch,
                          target_branch, source_image_uri, payload_uri)
    else:
        logging.warning('cannot find source image for %s, %s', board,
                        source_release)


def generate_test_image_npo_nmo_list(board, tested_release, test_nmo,
                                     test_npo, src_as_payload):
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
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).

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
        # Only add test configs we were asked to test.
        if (delta_type == 'npo' and not test_npo) or (delta_type == 'nmo' and
                                                      not test_nmo):
          continue

        if delta_type in found:
            raise FullReleaseTestError('more than one %s deltas found (%s, %s)',
                                       delta_type, board, tested_release)
        found.add(delta_type)

        # Generate test configuration.
        test_list.append(generate_test_image_config(
                board, delta_type, False, True, source_release, target_release,
                payload_uri, src_as_payload))

    return test_list


def generate_test_image_full_update_list(board, tested_release,
                                         source_releases, name, src_as_payload):
    """Generates test configurations of full updates with test images.

    Returns a list of test configurations from a given list of source releases
    to the given tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version
    @param sources_releases: list of source release versions
    @param name: name for generated test configurations
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the source/target pairs
            for the given board.

    """
    # If there are no source releases, there's nothing to do.
    if not source_releases:
        logging.warning("no '%s' source release provided for %s, %s; no tests "
                        "generated",
                        name, board, tested_release)
        return []

    # Find the full payload for the target release.
    tested_payload_uri = test_image.find_payload_uri(
            board, tested_release, get_release_branch(tested_release),
            single=True)
    if not tested_payload_uri:
        logging.warning("cannot find full payload for %s, %s; no '%s' tests "
                        "generated",
                        board, tested_release, name)
        return []

    # Construct test list.
    test_list = []
    for source_release in source_releases:
        test_config = generate_test_image_config(
                board, name, False, False,
                source_release, tested_release, tested_payload_uri,
                src_as_payload)
        if test_config:
            test_list.append(test_config)

    return test_list


def generate_test_image_fsi_list(board, tested_release, src_as_payload):
    """Generates FSI test configurations with test images.

    Returns a list of test configurations from FSI releases to the given
    tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version
    @param src_as_payload: if True, use the full payload as the src image as
        opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the FSI tests for the
            given board.

    """
    return generate_test_image_full_update_list(
            board, tested_release, _board_info.get_fsi_releases(board), 'fsi',
            src_as_payload)


def generate_test_image_specific_list(board, tested_release,
                                      specific_source_releases, src_as_payload):
    """Generates specific test configurations with test images.

    Returns a list of test configurations from a given list of source releases
    to the given tested release and board.

    @param board: the board under test
    @param tested_release: the tested release version
    @param specific_source_releases: list of source releases to test
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the given source
            releases.

    """
    return generate_test_image_full_update_list(
            board, tested_release, specific_source_releases, 'specific',
            src_as_payload)


def generate_npo_nmo_list(use_mp_images, board, tested_release, test_nmo,
                          test_npo, src_as_payload):
    """Generates N+1/N-1 test configurations.

    Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
    given tested release and board.

    @param use_mp_images: whether or not we're using MP-signed images
    @param logging: a logging object
    @param board: the board under test
    @param tested_release: the tested release version
    @param test_nmo: whether we should infer N-1 tests
    @param test_npo: whether we should infer N+1 tests
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the requested test
            types.

    @raise FullReleaseTestError if something went wrong

    """
    # Return N+1/N-1 test configurations.
    if use_mp_images:
        return generate_mp_image_npo_nmo_list(board, tested_release, test_nmo,
                                              test_npo)
    else:
        return generate_test_image_npo_nmo_list(board, tested_release,
                                                test_nmo, test_npo,
                                                src_as_payload)


def generate_fsi_list(use_mp_images, board, tested_release, src_as_payload):
    """Generates FSI test configurations.

    Returns a list of test configurations from FSI releases to the given
    tested release and board.

    @param use_mp_images: whether or not we're using MP-signed images
    @param board: the board under test
    @param tested_release: the tested release version
    @param src_as_payload: if True, use the full payload as the src image as
        opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the FSI tests for the
            given board.

    """
    if use_mp_images:
        return generate_mp_image_fsi_list(board, tested_release)
    else:
        return generate_test_image_fsi_list(board, tested_release,
                                            src_as_payload)


def generate_specific_list(use_mp_images, board, tested_release,
                           specific_source_releases, generated_tests,
                           src_as_payload):
    """Generates test configurations for a list of specific source releases.

    Returns a list of test configurations from a given list of releases to the
    given tested release and board. Cares to exclude test configurations that
    were already generated elsewhere (e.g. N-1/N+1, FSI).

    @param use_mp_images: whether or not we're using MP-signed images
    @param board: the board under test
    @param tested_release: the tested release version
    @param specific_source_releases: list of source release to test
    @param generated_tests: already generated test configuration
    @param src_as_payload: if True, use the full payload as the src image as
           opposed to using the test image (the latter requires servo).

    @return List of TestConfig objects corresponding to the specific source
            releases, minus those that were already generated elsewhere.

    """
    generated_source_releases = [
            test_config.source_release for test_config in generated_tests]
    filtered_source_releases = [rel for rel in specific_source_releases
                                if rel not in generated_source_releases]
    if use_mp_images:
        return generate_mp_image_specific_list(
                board, tested_release, filtered_source_releases)
    else:
        return generate_test_image_specific_list(
                board, tested_release, filtered_source_releases,
                src_as_payload)


def generate_test_list(args):
    """Setup the test environment.

    @param args: execution arguments

    @return A list of test configurations.

    @raise FullReleaseTestError if anything went wrong.

    """
    # Initialize test list.
    test_list = []
    # Use the full payload of the source image as the src URI rather than the
    # test image when not using servo.
    src_as_payload = args.servo_host == None

    for board in args.tested_board_list:
        test_list_for_board = []

        # Configure N-1-to-N and N-to-N+1 tests.
        if args.test_nmo or args.test_npo:
            test_list_for_board += generate_npo_nmo_list(
                    args.use_mp_images, board, args.tested_release,
                    args.test_nmo, args.test_npo, src_as_payload)

        # Configure FSI tests.
        if args.test_fsi:
            test_list_for_board += generate_fsi_list(
                    args.use_mp_images, board, args.tested_release,
                    src_as_payload)

        # Add tests for specifically provided source releases.
        if args.specific:
            test_list_for_board += generate_specific_list(
                    args.use_mp_images, board, args.tested_release,
                    args.specific, test_list_for_board, src_as_payload)

        test_list += test_list_for_board

    return test_list


def run_test_local(test, env, remote):
    """Run an end-to-end update test locally.

    @param test: the test configuration
    @param env: environment arguments for the test
    @param remote: remote DUT address

    """
    cmd = ['run_remote_tests.sh',
           '--args=%s%s' % (test.get_cmdline_args(), env.get_cmdline_args()),
           '--remote=%s' % remote,
           '--use_emerged',
           _autotest_test_name]

    # Only set servo arguments if servo is in the environment.
    if env.is_var_set('servo_host'):
        cmd.extend(['--servo', '--allow_offline_remote'])

    logging.debug('executing: %s', ' '.join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError, e:
        raise FullReleaseTestError(
                'command execution failed: %s' % e)


def run_test_afe(test, env, control_code, afe, dry_run):
    """Run an end-to-end update test via AFE.

    @param test: the test configuration
    @param env: environment arguments for the test
    @param control_code: content of the test control file
    @param afe: instance of server.frontend.AFE to use to create job.
    @param dry_run: If True, don't actually run the test against the afe.

    @return The scheduled job ID or None if dry_run.

    """
    # Parametrize the control script.
    parametrized_control_code = (
            test.get_code_args() + env.get_code_args() + control_code)

    # Create the job.
    meta_hosts = ['board:%s' % test.board]

    # Only set servo arguments if servo is in the environment.
    dependencies = ['servo'] if env.is_var_set('servo_host') else []
    logging.debug('scheduling afe test: meta_hosts=%s dependencies=%s',
                  meta_hosts, dependencies)
    if not dry_run:
        job = afe.create_job(
                parametrized_control_code,
                name=test.get_autotest_name(), priority='Medium',
                control_type='Server', meta_hosts=meta_hosts,
                dependencies=dependencies)
        return job.id
    else:
        logging.info('Would have run scheduled test %s against afe', test.name)


def get_job_url(server, job_id):
    """Returns the url for a given job status.

    @param server: autotest server.
    @param job_id: job id for the job created.

    @return the url the caller can use to track the job status.
    """
    # Explicitly print as this is what a caller looks for.
    return 'Job submitted to autotest afe. To check its status go to: %s' % (
            _autotest_url_format % dict(host=server, job=job_id))


def parse_args():
    parser = optparse.OptionParser(
            usage='Usage: %prog [options] RELEASE BOARD...',
            description='Schedule Chrome OS release update tests on given '
                        'board(s).')

    parser.add_option('--nmo', dest='test_nmo', action='store_true',
                      help='generate N-1 update tests')
    parser.add_option('--npo', dest='test_npo', action='store_true',
                      help='generate N+1 update tests')
    parser.add_option('--fsi', dest='test_fsi', action='store_true',
                      help='generate FSI update tests')
    parser.add_option('--specific', metavar='LIST',
                      help='comma-separated list of source releases to '
                           'generate test configurations from')
    parser.add_option('--servo_host', metavar='ADDR',
                      help='host running servod. Servo used only if set.')
    parser.add_option('--servo_port', metavar='PORT',
                      help='servod port [servod default]')
    parser.add_option('--omaha_host', metavar='ADDR',
                      help='Optional host where Omaha server will be spawned.'
                      'If not set, localhost is used.')
    parser.add_option('--mp_images', dest='use_mp_images', action='store_true',
                      help='use MP-signed images')
    parser.add_option('--remote', metavar='ADDR',
                      help='run test on given DUT via run_remote_tests')
    parser.add_option('-n', '--dry_run', action='store_true',
                      help='do not invoke actual test runs')
    parser.add_option('--log', metavar='LEVEL', dest='log_level',
                      default=_log_verbose,
                      help='verbosity level: %s' % ' '.join(_valid_log_levels))

    # Parse arguments.
    opts, args = parser.parse_args()

    # Get positional arguments, adding them as option values.
    if len(args) < 2:
        parser.error('missing arguments')

    opts.tested_release = args[0]
    opts.tested_board_list = args[1:]

    # Sanity check board.
    for board in opts.tested_board_list:
        if board not in _board_info.get_board_names():
            parser.error('unknown board (%s)' % board)

    # Sanity check log level.
    if opts.log_level not in _valid_log_levels:
        parser.error('invalid log level (%s)' % opts.log_level)

    # Process list of specific source releases.
    opts.specific = opts.specific.split(',') if opts.specific else []

    return opts


def main():
    try:
        # Initialize board/release configs.
        _board_info.initialize()
        _release_info.initialize()

        # Parse command-line arguments.
        args = parse_args()

        # Set log verbosity.
        if args.log_level == _log_debug:
            logging.basicConfig(level=logging.DEBUG)
        elif args.log_level == _log_verbose:
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
                if not args.dry_run:
                    run_test_local(test, env, args.remote)
        else:
            # Obtain the test control file content.
            control_file = os.path.join(
                    common.autotest_dir, 'server', 'site_tests',
                    _autotest_test_name, 'control')
            with open(control_file) as f:
                control_code = f.read()

            # Schedule jobs via AFE.
            afe = frontend.AFE(debug=(args.log_level == _log_debug))
            for i, test in enumerate(test_list):
                logging.info('scheduling test %d/%d:\n%r', i + 1,
                             len(test_list), test)
                job_id = run_test_afe(test, env, control_code,
                                      afe, args.dry_run)
                if job_id:
                    # Explicitly print as this is what a caller looks for.
                    print get_job_url(afe.server, job_id)

    except FullReleaseTestError, e:
        logging.fatal(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
