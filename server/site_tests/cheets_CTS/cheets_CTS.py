# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# repohooks/pre-upload.py currently does not run pylint. But for developers who
# want to check their code manually we disable several harmless pylint warnings
# which just distract from more serious remaining issues.
#
# The instance variable _android_cts is not defined in __init__().
# pylint: disable=attribute-defined-outside-init
#
# Many short variable names don't follow the naming convention.
# pylint: disable=invalid-name

import contextlib
import logging
import os
import shutil

from autotest_lib.client.common_lib import error
from autotest_lib.server import utils
from autotest_lib.server.cros import tradefed_test

# Notice if there are only a few failures each RETRY step currently (08/01/2016)
# takes a bit more than 6 minutes (mostly for reboot, login, starting ARC).
# In other words a RETRY of 10 takes about 1h, which is well within the limit of
# the 4h TIMEOUT. Nevertheless RETRY steps will cause the test to end with a
# test warning and should be treated as serious bugs.
# Finally, if we have a true test hang or even reboot, tradefed currently will
# likely hang unit the TIMEOUT hits and no RETRY steps will happen.
_CTS_MAX_RETRY = {'dev': 9, 'beta': 9, 'stable': 9}
# Maximum default time allowed for each individual CTS package.
_CTS_TIMEOUT_SECONDS = (4 * 3600)

# Public download locations for android cts bundles.
_DL_CTS = 'https://dl.google.com/dl/android/cts/'
_CTS_URI = {
    'arm' : _DL_CTS + 'android-cts-6.0_r9-linux_x86-arm.zip',
    'x86' : _DL_CTS + 'android-cts-6.0_r9-linux_x86-x86.zip',
    'media' : _DL_CTS + 'android-cts-media-1.1.zip'
}


@contextlib.contextmanager
def pushd(d):
    """Defines pushd."""
    current = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(current)


class cheets_CTS(tradefed_test.TradefedTest):
    """Sets up tradefed to run CTS tests."""
    version = 1

    def setup(self, bundle=None, uri=None):
        """Download and install a zipfile bundle from Google Storage.

        @param bundle: bundle name, which needs to be key of the _CTS_URI
                       dictionary. Can be 'arm', 'x86' and undefined.
        @param uri: URI of CTS bundle. Required if |abi| is undefined.
        """
        if bundle in _CTS_URI:
            self._android_cts = self._install_bundle(_CTS_URI[bundle])
        else:
            self._android_cts = self._install_bundle(uri)

        self._cts_tradefed = os.path.join(
                self._android_cts,
                'android-cts',
                'tools',
                'cts-tradefed')
        logging.info('CTS-tradefed path: %s', self._cts_tradefed)
        self._needs_push_media = False

    def _clean_repository(self):
        """Ensures all old logs, results and plans are deleted.

        This function should be called at the start of each autotest iteration.
        """
        logging.info('Cleaning up repository.')
        repository = os.path.join(self._android_cts, 'android-cts',
                'repository')
        for directory in ['logs', 'plans', 'results']:
            path = os.path.join(repository, directory)
            if os.path.exists(path):
                shutil.rmtree(path)
            self._safe_makedirs(path)

    def _push_media(self):
        """Downloads, caches and pushed media files to DUT."""
        media = self._install_bundle(_CTS_URI['media'])
        base = os.path.splitext(os.path.basename(_CTS_URI['media']))[0]
        cts_media = os.path.join(media, base)
        copy_media = os.path.join(cts_media, 'copy_media.sh')
        with pushd(cts_media):
            self._run(
                'source',
                args=(copy_media, 'all'),
                timeout=7200,  # Wait at most 2h for download of media files.
                verbose=True,
                stdout_tee=utils.TEE_TO_LOGS,
                stderr_tee=utils.TEE_TO_LOGS)

    def _tradefed_run_command(self,
                              package=None,
                              derivedplan=None,
                              session_id=None):
        """Builds the CTS tradefed 'run' command line.

        There should be exactly one parameter which is not None:
        @param package: the name of test package to be run.
        @param derivedplan: name of derived plan to retry.
        @param session_id: tradefed session id to continue.
        @return: list of command tokens for the 'run' command.
        """
        if package is not None:
            cmd = ['run', 'cts', '--package', package]
        elif derivedplan is not None:
            cmd = ['run', 'cts', '--plan', derivedplan]
        elif session_id is not None:
            cmd = ['run', 'cts', '--continue-session', '%d' % session_id]
        else:
            raise error.TestError('Need to provide an argument.')
        # Automated media download is broken, so disable it. Instead we handle
        # this explicitly via _push_media(). This has the benefit of being
        # cached on the dev server. b/27245577
        cmd.append('--skip-media-download')
        # Only push media for tests that need it. b/29371037
        if self._needs_push_media:
            self._push_media()
            # copy_media.sh is not lazy, but we try to be.
            self._needs_push_media = False

        # If we are running outside of the lab we can collect more data.
        if not utils.is_in_container():
            logging.info('Running outside of lab, adding extra debug options.')
            cmd.append('--log-level-display=DEBUG')
            cmd.append('--screenshot-on-failure')
            cmd.append('--collect-deqp-logs')
        # At early stage, cts-tradefed tries to reboot the device by
        # "adb reboot" command. In a real Android device case, when the
        # rebooting is completed, adb connection is re-established
        # automatically, and cts-tradefed expects that behavior.
        # However, in ARC, it doesn't work, so the whole test process
        # is just stuck. Here, disable the feature.
        cmd.append('--disable-reboot')
        # Create a logcat file for each individual failure.
        cmd.append('--logcat-on-failure')
        return cmd

    def _run_cts_tradefed(self, commands, datetime_id=None):
        """Runs tradefed, collects logs and returns the result counts.

        Assumes that only last entry of |commands| actually runs tests and has
        interesting output (results, logs) for collection. Ignores all other
        commands for this purpose.

        @param commands: List of lists of command tokens.
        @param datetime_id: For 'continue' datetime of previous run is known.
                            Knowing it makes collecting logs more robust.
        @return: tuple of (tests, pass, fail, notexecuted) counts.
        """
        for command in commands:
            # Assume only last command actually runs tests and has interesting
            # output (results, logs) for collection.
            logging.info('RUN: ./cts-tradefed %s', ' '.join(command))
            output = self._run(
                self._cts_tradefed,
                args=tuple(command),
                timeout=self._timeout,
                verbose=True,
                # Make sure to tee tradefed stdout/stderr to autotest logs
                # continuously during the test run.
                stdout_tee=utils.TEE_TO_LOGS,
                stderr_tee=utils.TEE_TO_LOGS)
            logging.info('END: ./cts-tradefed %s\n', ' '.join(command))
        if not datetime_id:
            # Parse stdout to obtain datetime of the session. This is needed to
            # locate result xml files and logs.
            datetime_id = self._parse_tradefed_datetime(output, self.summary)
        # Collect tradefed logs for autotest.
        tradefed = os.path.join(self._android_cts, 'android-cts', 'repository')
        autotest = os.path.join(self.resultsdir, 'android-cts')
        self._collect_logs(tradefed, datetime_id, autotest)
        return self._parse_result(output)

    def _tradefed_run(self, package):
        """Executes 'tradefed run |package|' command.

        @param package: the name of test package to be run.
        @return: tuple of (tests, pass, fail, notexecuted) counts.
        """
        # The list command is not required. It allows the reader to inspect the
        # tradefed state when examining the autotest logs.
        commands = [
                ['list', 'results'],
                self._tradefed_run_command(package=package)]
        return self._run_cts_tradefed(commands)

    def _tradefed_continue(self, session_id, datetime_id=None):
        """Continues a previously started session.

        Attempts to run all 'notexecuted' tests.
        @param session_id: tradefed session id to continue.
        @param datetime_id: datetime of run to continue.
        @return: tuple of (tests, pass, fail, notexecuted) counts.
        """
        # The list command is not required. It allows the reader to inspect the
        # tradefed state when examining the autotest logs.
        commands = [
                ['list', 'results'],
                self._tradefed_run_command(session_id=session_id)]
        return self._run_cts_tradefed(commands, datetime_id)

    def _tradefed_retry(self, package, session_id):
        """Retries failing tests in session.

        It is assumed that there are no notexecuted tests of session_id,
        otherwise some tests will be missed and never run.

        @param package: the name of test package to be run.
        @param session_id: tradefed session id to retry.
        @return: tuple of (new session_id, tests, pass, fail, notexecuted).
        """
        # Creating new test plan for retry.
        derivedplan = 'retry.%s.%s' % (package, session_id)
        logging.info('Retrying failures using derived plan %s.', derivedplan)
        # The list commands are not required. It allows the reader to inspect
        # the tradefed state when examining the autotest logs.
        commands = [
                ['list', 'plans'],
                ['add', 'derivedplan', '--plan', derivedplan, '--session', '%d'
                        % session_id, '-r', 'fail'],
                ['list', 'plans'],
                ['list', 'results'],
                self._tradefed_run_command(derivedplan=derivedplan)]
        tests, passed, failed, notexecuted = self._run_cts_tradefed(commands)
        # TODO(ihf): Consider if diffing/parsing output of "list results" for
        # new session_id might be more reliable. For now just assume simple
        # increment. This works if only one tradefed instance is active and
        # only a single run command is executing at any moment.
        session_id += 1
        return session_id, tests, passed, failed, notexecuted

    def _get_release_channel(self):
        """Returns the DUT channel of the image ('dev', 'beta', 'stable')."""
        # TODO(ihf): check CHROMEOS_RELEASE_DESCRIPTION and return channel.
        return 'dev'

    def _get_channel_retry(self):
        """Returns the maximum number of retries for DUT image channel."""
        channel = self._get_release_channel()
        if channel in _CTS_MAX_RETRY:
            return _CTS_MAX_RETRY[channel]
        retry = _CTS_MAX_RETRY['dev']
        logging.warning('Could not establish channel. Using retry=%d.', retry)
        return retry

    def run_once(self,
                 target_package,
                 max_retry=None,
                 timeout=_CTS_TIMEOUT_SECONDS):
        """Runs CTS |target_package| once, but with several retries.

        @param target_package: the name of test package to run.
        @param max_retry: number of retry steps before reporting results.
        @param timeout: time after which tradefed can be interrupted.
        """
        # On dev and beta channels timeouts are sharp, lenient on stable.
        self._timeout = timeout
        if self._get_release_channel == 'stable':
            self._timeout += 3600
        # Retries depend on target_package and channel.
        self._max_retry = max_retry
        if not self._max_retry:
            self._max_retry = self._get_channel_retry()
        self.summary = ''
        session_id = 0
        # Don't download media for tests that don't need it. b/29371037
        if target_package.startswith('android.mediastress'):
            self._needs_push_media = True
        # Unconditionally run CTS package.
        with self._login_chrome():
            self._ready_arc()
            # Start each iteration with a clean repository. This allows us to
            # track session_id blindly.
            self._clean_repository()
            logging.info('Running %s:', target_package)
            tests, passed, failed, notexecuted = self._tradefed_run(
                    target_package)
            logging.info('RESULT: tests=%d, passed=%d, failed=%d, notexecuted='
                    '%d', tests, passed, failed, notexecuted)
            self.summary = ('run(t=%d, p=%d, f=%d, ne=%d)' %
                    (tests, passed, failed, notexecuted))
            # An internal self-check. We really should never hit this.
            if tests != passed + failed + notexecuted:
                raise error.TestError(
                        'Test count inconsistent. %s' % self.summary)
            # Keep track of global counts as each step works on local failures.
            total_tests = tests
            total_passed = passed
        # The DUT has rebooted at this point and is in a clean state.

        # If the results were not completed or were failing then continue or
        # retry them iteratively MAX_RETRY times.
        steps = 0
        while steps < self._max_retry and (notexecuted > 0 or failed > 0):
            # First retry until there is no test is left that was not executed.
            while notexecuted > 0 and steps < self._max_retry:
                with self._login_chrome():
                    steps += 1
                    self._ready_arc()
                    logging.info('Continuing session %d:', session_id)
                    # 'Continue' reports as passed all passing results in the
                    # current session (including all tests passing before
                    # continue). Hence first subtract the old count before
                    # adding the new count. (Same for failed.)
                    previously_passed = passed
                    previously_failed = failed
                    previously_notexecuted = notexecuted
                    # TODO(ihf): For increased robustness pass in datetime_id of
                    # session we are continuing.
                    tests, passed, failed, notexecuted = self._tradefed_continue(
                            session_id)
                    # Unfortunately tradefed sometimes encounters an error
                    # running the tests for instance timing out on downloading
                    # the media files. Check for this condition and give it one
                    # extra chance.
                    if not (tests == previously_notexecuted and
                            tests == passed + failed + notexecuted):
                        logging.warning('Tradefed inconsistency - retrying.')
                        tests, passed, failed, notexecuted = self._tradefed_continue(
                                session_id)
                    newly_passed = passed - previously_passed
                    newly_failed = failed - previously_failed
                    total_passed += newly_passed
                    logging.info('RESULT: total_tests=%d, total_passed=%d, step'
                            '(tests=%d, passed=%d, failed=%d, notexecuted=%d)',
                            total_tests, total_passed, tests, newly_passed,
                            newly_failed, notexecuted)
                    self.summary += ' cont(t=%d, p=%d, f=%d, ne=%d)' % (tests,
                            newly_passed, newly_failed, notexecuted)
                    # An internal self-check. We really should never hit this.
                    if not (tests == previously_notexecuted and
                            tests == newly_passed + newly_failed + notexecuted):
                        logging.warning('Test count inconsistent. %s',
                                self.summary)
                # The DUT has rebooted at this point and is in a clean state.

            if notexecuted > 0:
                # This likely means there were too many crashes/reboots to
                # attempt running all tests. Don't attempt to retry as it is
                # impossible to pass at this stage (and also inconsistent).
                raise error.TestFail('Fail: Ran out of steps with %d total '
                        'passed and %d remaining not executed tests. %s' %
                        (total_passed, notexecuted, self.summary))

            # Managed to reduce notexecuted to zero. Now create a new test plan
            # to rerun only the failures we did encounter.
            if failed > 0:
                with self._login_chrome():
                    steps += 1
                    self._ready_arc()
                    logging.info('Retrying failures of %s with session_id %d:',
                            target_package, session_id)
                    previously_failed = failed
                    session_id, tests, passed, failed, notexecuted = self._tradefed_retry(
                            target_package, session_id)
                    # Unfortunately tradefed sometimes encounters an error
                    # running the tests for instance timing out on downloading
                    # the media files. Check for this condition and give it one
                    # extra chance.
                    if not (tests == previously_failed and
                            tests == passed + failed + notexecuted):
                        logging.warning('Tradefed inconsistency - retrying.')
                        session_id, tests, passed, failed, notexecuted = self._tradefed_retry(
                                target_package, session_id)
                    total_passed += passed
                    logging.info('RESULT: total_tests=%d, total_passed=%d, step'
                            '(tests=%d, passed=%d, failed=%d, notexecuted=%d)',
                            total_tests, total_passed, tests, passed, failed,
                            notexecuted)
                    self.summary += ' retry(t=%d, p=%d, f=%d, ne=%d)' % (tests,
                            passed, failed, notexecuted)
                    # An internal self-check. We really should never hit this.
                    if not (previously_failed == tests and
                            tests == passed + failed + notexecuted):
                        logging.warning('Test count inconsistent. %s',
                                self.summary)
                # The DUT has rebooted at this point and is in a clean state.

        # Final classification of test results.
        if notexecuted > 0 or failed > 0:
            raise error.TestFail('Failed: after %d retries giving up. '
                    'total_passed=%d, failed=%d, notexecuted=%d. %s' % (steps,
                    total_passed, failed, notexecuted, self.summary))
        if steps > 0:
            raise error.TestWarn('Passed: after %d retries passing %d tests. %s'
                    % (steps, total_passed, self.summary))