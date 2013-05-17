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
import re
import subprocess
import sys

import common
from autotest_lib.client.common_lib import control_data
from autotest_lib.server import frontend
from autotest_lib.site_utils.autoupdate import board as board_util
from autotest_lib.site_utils.autoupdate import release as release_util
from autotest_lib.site_utils.autoupdate import test_image

# Autotest pylint is more restrictive than it should with args.
#pylint: disable=C0111


# Global reference objects.
_board_info = board_util.BoardInfo()
_release_info = release_util.ReleaseInfo()

_log_debug = 'debug'
_log_normal = 'normal'
_log_verbose = 'verbose'
_valid_log_levels = _log_debug, _log_normal, _log_verbose
_autotest_url_format = r'http://%(host)s/afe/#tab_id=view_job&object_id=%(job)s'
_autotest_test_name = 'autoupdate_EndToEndTest'
_autoupdate_suite_name = 'au'
_default_dump_dir = os.path.realpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'server',
                     'site_tests', _autotest_test_name))
# Matches delta format name and returns groups for branches and release numbers.
_delta_re = re.compile(
        'chromeos_'
        '(?P<s_version>R[0-9]+-[0-9a-z.\-]+)_'
        '(?P<t_version>R[0-9]+-[0-9a-z.\-]+)_[\w.]+')

_build_version_re = re.compile(
        '(?P<branch>R[0-9]+)-(?P<release>[0-9a-z.\-]+)')
_build_version = '%(branch)s-%(release)s'


# Extracts just the main version from a version that may contain attempts or
# a release candidate suffix i.e. 3928.0.0-a2 -> base_version=3928.0.0.
_version_re = re.compile('(?P<base_version>[0-9.]+)(?:\-[a-z]+[0-9]+])*')



_name_re = re.compile('\s*NAME\s*=')


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
                 source_release, target_release, source_image_uri,
                 target_payload_uri):
        """Initialize a test configuration.

        @param board: the board being tested (e.g. 'x86-alex')
        @param name: a descriptive name of the test
        @param use_mp_images: whether or not we're using test images (Boolean)
        @param is_delta_update: whether this is a delta update test (Boolean)
        @param source_release: the source image version (e.g. '2672.0.0')
        @param target_release: the target image version (e.g. '2673.0.0')
        @param source_image_uri: source image URI ('gs://...')
        @param target_payload_uri: target payload URI ('gs://...')

        """
        self.board = board
        self.name = name
        self.use_mp_images = use_mp_images
        self.is_delta_update = is_delta_update
        self.source_release = source_release
        self.target_release = target_release
        self.source_image_uri = source_image_uri
        self.target_payload_uri = target_payload_uri


    def get_image_type(self):
        return 'mp' if self.use_mp_images else 'test'


    def get_update_type(self):
        return 'delta' if self.is_delta_update else 'full'


    def unique_name_suffix(self):
        """Unique name suffix for the test config given the target version."""
        return '%s_%s' % (self.name, self.source_release)


    def get_autotest_name(self):
        """Returns job name to use when creating an autotest job.

        Returns a job name that conforms to the suite naming style assuming
        'au' is the suite name.
        """
        return '%s-release/%s/au/%s.%s' % (
                self.board, self.target_release,
                _autotest_test_name, self.unique_name_suffix())


    def get_control_file_name(self):
        """Returns the name of the name of the control file to store this in.

        Returns the control file name that should be generated for this test.
        A unique name suffix is used to keep from collisions per target
        release/board.
        """
        return 'control.%s' % self.unique_name_suffix()


    def __str__(self):
        """Short textual representation w/o image/payload URIs."""
        return ('[%s/%s/%s/%s/%s -> %s]' %
                (self.board, self.name, self.get_image_type(),
                 self.get_update_type(), self.source_release,
                 self.target_release))


    def __repr__(self):
        """Full textual representation w/ image/payload URIs."""
        return '\n'.join([str(self),
                          'source image   : %s' % self.source_image_uri,
                          'target payload : %s' % self.target_payload_uri])


    def _get_args(self, assign, delim, is_quote_val):
        template = "%s%s'%s'" if is_quote_val else "%s%s%s"
        return delim.join(
                [template % (key, assign, val) for key, val in [
                        ('name', self.name),
                        ('image_type', self.get_image_type()),
                        ('update_type', self.get_update_type()),
                        ('source_release', self.source_release),
                        ('target_release', self.target_release),
                        ('source_image_uri', self.source_image_uri),
                        ('target_payload_uri', self.target_payload_uri),
                        ('SUITE', _autoupdate_suite_name)]])


    def get_cmdline_args(self):
        return self._get_args('=', ' ', False)


    def get_code_args(self):
        args = self._get_args(' = ', '\n', True)
        return args + '\n' if args else ''


def get_release_branch(release):
    """Returns the release branch for the given release.

    @param release: release version e.g. 3920.0.0.

    @returns the branch string e.g. R26.
    """
    return _release_info.get_branch(release)


class TestConfigGenerator(object):
    """Class for generating test configs."""

    def __init__(self, board, tested_release, test_nmo, test_npo,
                 src_as_payload, use_mp_images, archive_url=None):
        """
        @param board: the board under test
        @param tested_release: the tested release version
        @param test_nmo: whether we should infer N-1 tests
        @param test_npo: whether we should infer N+1 tests
        @param src_as_payload: if True, use the full payload as the src image as
               opposed to using the test image (the latter requires servo).
        @param use_mp_images: use mp images/payloads.
        @param archive_url: optional gs url to find payloads.

        """
        self.board = board
        self.tested_release = tested_release
        self.test_nmo = test_nmo
        self.test_npo = test_npo
        self.src_as_payload = src_as_payload
        self.use_mp_images = use_mp_images
        if archive_url:
            self.archive_url = archive_url
        else:
            branch = get_release_branch(tested_release)
            build_version = _build_version % dict(branch=branch,
                                                  release=tested_release)
            self.archive_url = test_image.get_default_archive_url(
                    board, build_version)

        # Get the prefix which is an archive_url stripped of its trailing
        # version. We rstrip in the case of any trailing /'s.
        # Use archive prefix for any nmo / specific builds.
        self.archive_prefix = self.archive_url.rstrip('/').rpartition('/')[0]


    def _get_source_uri_from_build_version(self, build_version):
        """Returns the source_url given build version.

        Args:
            build_version: the full build version i.e. R27-3823.0.0-a2.
        """
        # If we're looking for our own image, use the target archive_url if set
        if self.tested_release in build_version:
            archive_url = self.archive_url
        else:
            archive_url = test_image.get_archive_url_from_prefix(
                    self.archive_prefix, build_version)

        if self.src_as_payload:
            return test_image.find_payload_uri(archive_url, single=True)
        else:
            return test_image.find_image_uri(archive_url)


    def _get_source_uri_from_release(self, release):
        """Returns the source uri for a given release or None if not found.

        Args:
            release: required release number.
        """
        branch = get_release_branch(release)
        return self._get_source_uri_from_build_version(
                _build_version % dict(branch=branch, release=release))


    def generate_mp_image_npo_nmo_list(self):
        """Generates N+1/N-1 test configurations with MP-signed images.

        Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
        given tested release and board.

        @return A pair of TestConfig objects corresponding to the N+1 and N-1
                tests.

        @raise FullReleaseTestError if something went wrong

        """
        # TODO(garnold) generate N+/-1 configurations for MP-signed images.
        raise NotImplementedError(
                'generation of mp-signed test configs not implemented')


    def generate_mp_image_fsi_list(self):
        """Generates FSI test configurations with MP-signed images."""
        # TODO(garnold) configure FSI-to-N delta tests for MP-signed images.
        raise NotImplementedError(
            'generation of mp-signed test configs not implemented')


    def generate_mp_image_specific_list(self, specific_source_releases):
        """Generates specific test configurations with MP-signed images.

        Returns a list of test configurations from a given list of source
        releases to the given tested release and board.

        @param specific_source_releases: list of source releases to test

        @return List of TestConfig objects corresponding to the given source
                releases.

        """
        # TODO(garnold) configure FSI-to-N delta tests for MP-signed images.
        raise NotImplementedError(
            'generation of mp-signed test configs not implemented')


    def generate_test_image_config(self, name, is_delta_update, source_release,
                                   payload_uri, source_uri):
        """Constructs a single test config with given arguments.

        It'll automatically find and populate source/target branches as well as
        the source image URI.

        @param name: a descriptive name for the test
        @param is_delta_update: whether we're testing a delta update
        @param source_release: the version of the source image (before update)
        @param target_release: the version of the target image (after update)
        @param payload_uri: URI of the update payload.
        @param source_uri:  URI of the source image/payload.

        """
        # Pass only the base versions without any build specific suffixes.
        source_version = _version_re.match(source_release).group('base_version')
        target_version = _version_re.match(self.tested_release).group(
                'base_version')
        return TestConfig(
                self.board, name, self.use_mp_images, is_delta_update,
                source_version, target_version, source_uri, payload_uri)


    @staticmethod
    def _parse_build_version(build_version):
        """Returns a branch, release tuple from a full build_version.

        Args:
            build_version: Delta filename to parse e.g.
                      'chromeos_R27-3905.0.0_R27-3905.0.0_stumpy_delta_dev.bin'
        """
        match = _build_version_re.match(build_version)
        if not match:
            logging.warn('version %s did not match version format',
                         build_version)
            return None

        return match.group('branch'), match.group('release')


    @staticmethod
    def _parse_delta_filename(filename):
        """Parses a delta payload name into its source/target versions.

        Args:
            filename: Delta filename to parse e.g.
                      'chromeos_R27-3905.0.0_R27-3905.0.0_stumpy_delta_dev.bin'

        Returns: tuple with source_version, and target_version.
        """
        match = _delta_re.match(filename)
        if not match:
            logging.warn('filename %s did not match delta format', filename)
            return None

        return match.group('s_version'), match.group('t_version')


    def generate_test_image_npo_nmo_list(self):
        """Generates N+1/N-1 test configurations with test images.

        Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
        given tested release and board. This is done by scanning of the test
        image repository, looking for update payloads; normally, we expect to
        find at most one update payload of each of the aforementioned types.

        @return A list of TestConfig objects corresponding to the N+1 and N-1
                tests.

        @raise FullReleaseTestError if something went wrong

        """
        if not (self.test_nmo or self.test_npo):
            return []

        # Find all test delta payloads involving the release version at hand,
        # then figure out which is which.
        found = set()
        test_list = []
        payload_uri_list = test_image.find_payload_uri(
                self.archive_url, delta=True)
        for payload_uri in payload_uri_list:
            # Infer the source and target release versions.
            file_name = os.path.basename(payload_uri)
            source_version, target_version = (
                    self._parse_delta_filename(file_name))
            _, source_release = self._parse_build_version(source_version)

            # The target version should contain the tested release otherwise
            # this is a malformed delta i.e. 940.0.1 in R28-940.0.1-a1.
            if self.tested_release not in target_version:
                raise FullReleaseTestError(
                        'delta target release %s does not contain %s (%s)',
                        target_version, self.tested_release, self.board)

            source_uri = self._get_source_uri_from_build_version(source_version)
            if not source_uri:
                logging.warning('cannot find source for %s, %s', self.board,
                                source_version)
                continue

            # Determine delta type, make sure it was not already discovered.
            delta_type = 'npo' if source_version == target_version else 'nmo'
            # Only add test configs we were asked to test.
            if (delta_type == 'npo' and not self.test_npo) or (
                delta_type == 'nmo' and not self.test_nmo):
                continue

            if delta_type in found:
                raise FullReleaseTestError(
                        'more than one %s deltas found (%s, %s)' % (
                        delta_type, self.board, self.tested_release))

            found.add(delta_type)

            # Generate test configuration.
            test_list.append(self.generate_test_image_config(
                    delta_type, True, source_release, payload_uri, source_uri))

        return test_list


    def generate_test_image_full_update_list(self, source_releases, name):
        """Generates test configurations of full updates with test images.

        Returns a list of test configurations from a given list of source
        releases to the given tested release and board.

        @param sources_releases: list of source release versions
        @param name: name for generated test configurations

        @return List of TestConfig objects corresponding to the source/target
                pairs for the given board.

        """
        # If there are no source releases, there's nothing to do.
        if not source_releases:
            logging.warning("no '%s' source release provided for %s, %s; no "
                            "tests generated",
                            name, self.board, self.tested_release)
            return []

        # Find the full payload for the target release.
        tested_payload_uri = test_image.find_payload_uri(
                self.archive_url, single=True)
        if not tested_payload_uri:
            logging.warning("cannot find full payload for %s, %s; no '%s' tests"
                            " generated", self.board, self.tested_release, name)
            return []

        # Construct test list.
        test_list = []
        for source_release in source_releases:
            source_uri = self._get_source_uri_from_release(source_release)
            if not source_uri:
                logging.warning('cannot find source for %s, %s', self.board,
                                source_release)
                continue

            test_list.append(self.generate_test_image_config(
                    name, False, source_release, tested_payload_uri,
                    source_uri))

        return test_list


    def generate_test_image_fsi_list(self):
        """Generates FSI test configurations with test images.

        Returns a list of test configurations from FSI releases to the given
        tested release and board.

        @return List of TestConfig objects corresponding to the FSI tests for
                the given board.

        """
        return self.generate_test_image_full_update_list(
                _board_info.get_fsi_releases(self.board), 'fsi')


    def generate_test_image_specific_list(self, specific_source_releases):
        """Generates specific test configurations with test images.

        Returns a list of test configurations from a given list of source
        releases to the given tested release and board.

        @param specific_source_releases: list of source releases to test

        @return List of TestConfig objects corresponding to the given source
                releases.

        """
        return self.generate_test_image_full_update_list(
                specific_source_releases, 'specific')


    def generate_npo_nmo_list(self):
        """Generates N+1/N-1 test configurations.

        Computes a list of N+1 (npo) and/or N-1 (nmo) test configurations for a
        given tested release and board.

        @return List of TestConfig objects corresponding to the requested test
                types.

        @raise FullReleaseTestError if something went wrong

        """
        # Return N+1/N-1 test configurations.
        if self.use_mp_images:
            return self.generate_mp_image_npo_nmo_list()
        else:
            return self.generate_test_image_npo_nmo_list()


    def generate_fsi_list(self):
        """Generates FSI test configurations.

        Returns a list of test configurations from FSI releases to the given
        tested release and board.

        @return List of TestConfig objects corresponding to the FSI tests for
                the given board.

        """
        if self.use_mp_images:
            return self.generate_mp_image_fsi_list()
        else:
            return self.generate_test_image_fsi_list()


    def generate_specific_list(self, specific_source_releases, generated_tests):
        """Generates test configurations for a list of specific source releases.

        Returns a list of test configurations from a given list of releases to
        the given tested release and board. Cares to exclude test configurations
        that were already generated elsewhere (e.g. N-1/N+1, FSI).

        @param specific_source_releases: list of source release to test
        @param generated_tests: already generated test configuration

        @return List of TestConfig objects corresponding to the specific source
                releases, minus those that were already generated elsewhere.

        """
        generated_source_releases = [
                test_config.source_release for test_config in generated_tests]
        filtered_source_releases = [rel for rel in specific_source_releases
                                    if rel not in generated_source_releases]
        if self.use_mp_images:
            return self.generate_mp_image_specific_list(
                    filtered_source_releases)
        else:
            return self.generate_test_image_specific_list(
                    filtered_source_releases)


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
        generator = TestConfigGenerator(
                board, args.tested_release,
                args.test_nmo, args.test_npo, src_as_payload,
                args.use_mp_images, args.archive_url)

        # Configure N-1-to-N and N-to-N+1 tests.
        if args.test_nmo or args.test_npo:
            test_list_for_board += generator.generate_npo_nmo_list()

        # Configure FSI tests.
        if args.test_fsi:
            test_list_for_board += generator.generate_fsi_list()

        # Add tests for specifically provided source releases.
        if args.specific:
            test_list_for_board += generator.generate_specific_list(
                    args.specific, test_list_for_board)

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


def generate_full_control_file(test, env, control_code):
    """Returns the parameterized control file for the test config.

    @param test: the test config.
    @param env: instance of TestEnv for the test.
    @param control_code: string containing the template control code.

    @returns parameterized control file based on args.
    """
    def add_name_suffix(code):
        """Replace NAME = in the control file with unique name for build."""
        new_code = []
        original_name = control_data.parse_control_string(code).name
        for line in code.splitlines():
            if _name_re.match(line):
                new_code.append('NAME = "%s_%s"' % (original_name,
                                                    test.unique_name_suffix()))
            else:
                new_code.append(line)

        # Splitlines and rejoining strips the trailing line. Trailing line
        # is needed by autotest.
        new_code.append('')
        return '\n'.join(new_code)

    control_code = add_name_suffix(control_code)
    return test.get_code_args() + env.get_code_args() + control_code


def dump_autotest_control_file(test, env, control_code, directory):
    """Creates control file for test and returns the path to created file.

    @param test: the test config.
    @param env: instance of TestEnv for the test.
    @param control_code: string containing the template control code.
    @param directory: the directory to dump the control file.

    @returns Path to the newly dumped control file.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

    parametrized_control_code = generate_full_control_file(
            test, env, control_code)

    control_file = os.path.join(directory,
                                test.get_control_file_name())
    with open(control_file, 'w') as fh:
        fh.write(parametrized_control_code)

    return control_file


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
    parametrized_control_code = generate_full_control_file(
            test, env, control_code)

    # Create the job.
    meta_hosts = ['board:%s' % test.board]

    # Only set servo arguments if servo is in the environment.
    dependencies = ['servo'] if env.is_var_set('servo_host') else []
    dependencies += ['pool:suites']
    logging.debug('scheduling afe test: meta_hosts=%s dependencies=%s',
                  meta_hosts, dependencies)
    if not dry_run:
        job = afe.create_job(
                parametrized_control_code,
                name=test.get_autotest_name(), priority='Low',
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
            usage='Usage: %prog [options] RELEASE [BOARD...]',
            description='Schedule Chrome OS release update tests on given '
                        'board(s).')

    parser.add_option('--all_boards', dest='all_boards', action='store_true',
                      help='default test run to all known boards')
    parser.add_option('--archive_url', metavar='URL',
                      help='Use this archive url to find the target payloads.')
    parser.add_option('--dump', default=False, action='store_true',
                      help='dump control files that would be used in autotest '
                           'without running them. Implies --dry_run')
    parser.add_option('--dump_dir', default=_default_dump_dir,
                      help='directory to dump control files generated')
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
    parser.add_option('--skip_boards', dest='skip_boards',
                      help='boards to skip, separated by comma.')
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
    if len(args) < 1:
        parser.error('missing arguments')

    opts.tested_release = args[0]
    opts.tested_board_list = args[1:]
    if not opts.tested_board_list and not opts.all_boards:
        parser.error('No boards listed.')
    if opts.tested_board_list and opts.all_boards:
        parser.error('--all_boards should not be used with individual board '
                     'arguments".')

    if opts.all_boards:
        opts.tested_board_list = _board_info.get_board_names()
    else:
        # Sanity check board.
        for board in opts.tested_board_list:
            if board not in _board_info.get_board_names():
                parser.error('unknown board (%s)' % board)

    # Skip specific board.
    if opts.skip_boards:
        opts.skip_boards = opts.skip_boards.split(',')
        opts.tested_board_list = [board for board in opts.tested_board_list
                                  if board not in opts.skip_boards]

    # Sanity check log level.
    if opts.log_level not in _valid_log_levels:
        parser.error('invalid log level (%s)' % opts.log_level)

    if opts.dump:
        if opts.remote:
            parser.error("--remote doesn't make sense with --dump")

        opts.dry_run = True

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

            if args.dump:
                for test in test_list:
                    # Control files for the same board are all in the same
                    # sub-dir.
                    directory = os.path.join(args.dump_dir, test.board)
                    control_file = dump_autotest_control_file(
                            test, env, control_code, directory)
                    logging.info('dumped control file for test %s to %s',
                                 test, control_file)

                return

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
