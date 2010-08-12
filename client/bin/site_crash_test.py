# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import site_log_reader, site_utils, test
from autotest_lib.client.common_lib import error, utils


class CrashTest(test.test):

    _CONSENT_FILE = '/home/chronos/Consent To Send Stats'
    _CRASH_REPORTER_PATH = '/sbin/crash_reporter'
    _CRASH_SENDER_PATH = '/sbin/crash_sender'
    _CRASH_SENDER_RATE_DIR = '/var/lib/crash_sender'
    _CRASH_SENDER_RUN_PATH = '/var/run/crash_sender.pid'
    _MOCK_CRASH_SENDING = '/tmp/mock-crash-sending'
    _PAUSE_FILE = '/tmp/pause-crash-sending'
    _SYSTEM_CRASH_DIR = '/var/spool/crash'
    _USER_CRASH_DIR = '/home/chronos/user/crash'

    def _set_sending(self, is_enabled):
        if is_enabled:
            if os.path.exists(self._PAUSE_FILE):
                os.remove(self._PAUSE_FILE)
        else:
            utils.system('touch ' + self._PAUSE_FILE)


    def _reset_rate_limiting(self):
        utils.system('rm -rf ' + self._CRASH_SENDER_RATE_DIR)


    def _clear_spooled_crashes(self):
        utils.system('rm -rf ' + self._SYSTEM_CRASH_DIR)
        utils.system('rm -rf ' + self._USER_CRASH_DIR)


    def _kill_running_sender(self):
        if not os.path.exists(self._CRASH_SENDER_RUN_PATH):
            return
        running_pid = int(utils.read_file(self._CRASH_SENDER_RUN_PATH))
        logging.warning('Detected running crash sender (%d), killing' %
                        running_pid)
        utils.system('kill -9 %d' % running_pid)
        os.remove(self._CRASH_SENDER_RUN_PATH)


    def _set_sending_mock(self, mock_enabled, send_success=True):
        if mock_enabled:
            if send_success:
                data = ''
            else:
                data = '1'
            logging.info('Setting sending mock')
            utils.open_write_close(self._MOCK_CRASH_SENDING, data)
        else:
            utils.system('rm -f ' + self._MOCK_CRASH_SENDING)


    def _set_consent(self, has_consent):
        if has_consent:
            utils.open_write_close(self._CONSENT_FILE, 'test-consent')
            logging.info('Created ' + self._CONSENT_FILE)
        else:
            utils.system('rm -f "%s"' % (self._CONSENT_FILE))


    def _get_pushed_consent_file_path(self):
        return os.path.join(self.bindir, 'pushed_consent')


    def _push_consent(self):
        if os.path.exists(self._CONSENT_FILE):
            os.rename(self._CONSENT_FILE, self._get_pushed_consent_file_path())


    def _pop_consent(self):
        self._set_consent(False)
        if os.path.exists(self._get_pushed_consent_file_path()):
            os.rename(self._get_pushed_consent_file_path(), self._CONSENT_FILE)


    def _get_crash_dir(self, username):
        if username == 'chronos':
            return self._USER_CRASH_DIR
        else:
            return self._SYSTEM_CRASH_DIR


    def _initialize_crash_reporter(self):
        utils.system('%s --init --nounclean_check' % self._CRASH_REPORTER_PATH)


    def _create_fake_crash_dir_entry(self, name):
        entry = os.path.join(self._SYSTEM_CRASH_DIR, name)
        if not os.path.exists(self._SYSTEM_CRASH_DIR):
            os.makedirs(self._SYSTEM_CRASH_DIR)
        utils.system('touch ' + entry)
        return entry


    def _prepare_sender_one_crash(self,
                                  send_success,
                                  reports_enabled,
                                  username,
                                  minidump):
        self._set_sending_mock(mock_enabled=True, send_success=send_success)
        self._set_consent(reports_enabled)
        if minidump is None:
            minidump = self._create_fake_crash_dir_entry('fake.dmp')
        return minidump


    def _parse_sender_output(self, output):
        """Parse the log output from the crash_sender script.

        This script can run on the logs from either a mocked or true
        crash send.

        Args:
          output: output from the script

        Returns:
          A dictionary with these values:
            send_attempt: did the script attempt to send a crash.
            send_success: if it attempted, was the crash send successful.
            sleep_time: if it attempted, how long did it sleep before
              sending (if mocked, how long would it have slept)
            output: the output from the script, copied
        """
        sleep_match = re.search('Scheduled to send in (\d+)s', output)
        send_attempt = sleep_match is not None
        if send_attempt:
            sleep_time = int(sleep_match.group(1))
        else:
            sleep_time = None
        send_success = 'Mocking successful send' in output
        return {'send_attempt': send_attempt,
                'send_success': send_success,
                'sleep_time': sleep_time,
                'output': output}


    def _call_sender_one_crash(self,
                               send_success=True,
                               reports_enabled=True,
                               username='root',
                               minidump=None):
        """Call the crash sender script to mock upload one crash.

        Args:
          send_success: Mock a successful send if true
          reports_enabled: Has the user consented to sending crash reports.
          username: user to emulate a crash from
          minidump: minidump to use for crash, if None we create one.

        Returns:
          Returns a dictionary describing the result with the keys
          from _parse_sender_output, as well as:
            minidump_exists: does the minidump still exist after calling
              send script
            rate_count: how many crashes have been uploaded in the past
              24 hours.
        """
        minidump = self._prepare_sender_one_crash(send_success,
                                                  reports_enabled,
                                                  username,
                                                  minidump)
        self._log_reader.set_start_by_current()
        script_output = utils.system_output(
            '/bin/sh -c "%s" 2>&1' % self._CRASH_SENDER_PATH,
            ignore_status=True)
        # Wait for up to 2s for no crash_sender to be running,
        # otherwise me might get only part of the output.
        site_utils.poll_for_condition(
            lambda: utils.system('pgrep crash_sender',
                                 ignore_status=True) != 0,
            timeout=2,
            exception=error.TestError(
              'Timeout waiting for crash_sender to finish: ' +
              self._log_reader.get_logs()))

        output = self._log_reader.get_logs()
        logging.debug('Crash sender message output:\n' + output)
        if script_output != '':
            raise error.TestFail(
                'Unexpected crash_sender stdout/stderr: ' + script_output)

        if os.path.exists(minidump):
            minidump_exists = True
            os.remove(minidump)
        else:
            minidump_exists = False
        if os.path.exists(self._CRASH_SENDER_RATE_DIR):
            rate_count = len(os.listdir(self._CRASH_SENDER_RATE_DIR))
        else:
            rate_count = 0

        result = self._parse_sender_output(output)
        result['minidump_exists'] = minidump_exists
        result['rate_count'] = rate_count

        # Show the result for debugging but remove 'output' key
        # since it's large and earlier in debug output.
        debug_result = dict(result)
        del debug_result['output']
        logging.debug('Result of send (besides output): %s' % debug_result)

        return result


    def initialize(self):
        test.test.initialize(self)
        self._log_reader = site_log_reader.LogReader()


    def cleanup(self):
        self._reset_rate_limiting()
        self._clear_spooled_crashes()
        self._set_sending(True)
        self._set_sending_mock(mock_enabled=False)
        self._pop_consent()
        test.test.cleanup(self)


    def run_crash_tests(self, test_names):
        self._push_consent()

        # Sanity check test_names is complete
        for attr in dir(self):
            if attr.find('_test_') == 0:
                test_name = attr[6:]
                if not test_name in test_names:
                    raise error.TestError('Test %s is missing' % test_name)

        for test_name in test_names:
            logging.info(('=' * 20) + ('Running %s' % test_name) + ('=' * 20))
            self._initialize_crash_reporter()
            self._kill_running_sender()
            self._reset_rate_limiting()
            self._clear_spooled_crashes()
            self._set_sending(False)
            getattr(self, '_test_' + test_name)()
