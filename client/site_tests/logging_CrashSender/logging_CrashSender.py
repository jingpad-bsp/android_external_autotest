# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import site_crash_test, site_utils, test
from autotest_lib.client.common_lib import error, utils

_CRASH_SENDER_CRON_PATH = '/etc/cron.hourly/crash_sender.hourly'
_DAILY_RATE_LIMIT = 8
_MIN_UNIQUE_TIMES = 4
_SECONDS_SEND_SPREAD = 3600


class logging_CrashSender(site_crash_test.CrashTest):
    version = 1


    def _test_sender_simple_minidump(self):
        """Test sending a single minidump crash report."""
        self._set_sending(True)
        result = self._call_sender_one_crash()
        if (result['report_exists'] or
            result['rate_count'] != 1 or
            not result['send_attempt'] or
            not result['send_success'] or
            result['sleep_time'] < 0 or
            result['sleep_time'] >= _SECONDS_SEND_SPREAD or
            result['report_kind'] != 'minidump' or
            result['exec_name'] != 'fake'):
            raise error.TestFail('Simple minidump send failed')


    def _test_sender_simple_kernel_crash(self):
        """Test sending a single kcrash report."""
        self._set_sending(True)
        kcrash_fake_report = self.create_fake_crash_dir_entry(
            'kernel.today.kcrash')
        result = self._call_sender_one_crash(report=kcrash_fake_report)
        if (result['report_exists'] or
            result['rate_count'] != 1 or
            not result['send_attempt'] or
            not result['send_success'] or
            result['sleep_time'] < 0 or
            result['sleep_time'] >= _SECONDS_SEND_SPREAD or
            result['report_kind'] != 'kcrash' or
            result['exec_name'] != 'kernel'):
            raise error.TestFail('Simple kcrash send failed')


    def _test_sender_pausing(self):
        """Test the sender returns immediately when the pause file is present.

        This is testing the sender's test functionality - if this regresses,
        other tests can become flaky because the cron-started sender may run
        asynchronously to these tests."""
        self._set_sending(False)
        result = self._call_sender_one_crash()
        if (not result['report_exists'] or
            not 'Exiting early due to' in result['output'] or
            result['send_attempt']):
            raise error.TestFail('Sender did not pause')


    def _test_sender_reports_disabled(self):
        """Test that when reporting is disabled, we don't send."""
        self._set_sending(True)
        result = self._call_sender_one_crash(reports_enabled=False)
        if (result['report_exists'] or
            not 'Uploading is disabled' in result['output'] or
            result['send_attempt']):
            raise error.TestFail('Sender did not handle reports disabled')


    def _test_sender_rate_limiting(self):
        """Test the sender properly rate limits and sends with delay."""
        self._set_sending(True)
        sleep_times = []
        for i in range(1, _DAILY_RATE_LIMIT + 1):
            result = self._call_sender_one_crash()
            if not result['send_attempt'] or not result['send_success']:
                raise error.TestFail('Crash uploader did not send on #%d' % i)
            if result['rate_count'] != i:
                raise error.TestFail('Did not properly persist rate on #%d' % i)
            sleep_times.append(result['sleep_time'])
        logging.debug('Sleeps between sending crashes were: %s' % sleep_times)
        unique_times = {}
        for i in range(0, _DAILY_RATE_LIMIT):
            unique_times[sleep_times[i]] = True
        if len(unique_times) < _MIN_UNIQUE_TIMES:
            raise error.TestFail('Expected at least %d unique times: %s' %
                                 _MIN_UNIQUE_TIMES, sleep_times)
        # Now the _DAILY_RATE_LIMIT ^ th send request should fail.
        result = self._call_sender_one_crash()
        if (not result['report_exists'] or
            not 'Cannot send more crashes' in result['output'] or
            result['rate_count'] != _DAILY_RATE_LIMIT):
            raise error.TestFail('Crash rate limiting did not take effect')

        # Set one rate file a day earlier and verify can send
        rate_files = os.listdir(self._CRASH_SENDER_RATE_DIR)
        rate_path = os.path.join(self._CRASH_SENDER_RATE_DIR, rate_files[0])
        statinfo = os.stat(rate_path)
        os.utime(rate_path, (statinfo.st_atime,
                             statinfo.st_mtime - (60 * 60 * 25)))
        utils.system('ls -l ' + self._CRASH_SENDER_RATE_DIR)
        result = self._call_sender_one_crash()
        if (not result['send_attempt'] or
            not result['send_success'] or
            result['rate_count'] != _DAILY_RATE_LIMIT):
            raise error.TestFail('Crash not sent even after 25hrs pass')


    def _test_sender_single_instance(self):
        """Test the sender fails to start when another instance is running.

        Here we rely on the sender not checking the other running pid
        is of the same instance.
        """
        self._set_sending(True)
        utils.open_write_close(self._CRASH_SENDER_RUN_PATH, str(os.getpid()))
        result = self._call_sender_one_crash()
        if (not 'Already running.' in result['output'] or
            result['send_attempt'] or not result['report_exists']):
            raise error.TestFail('Allowed multiple instances to run')
        os.remove(self._CRASH_SENDER_RUN_PATH)


    def _test_sender_send_fails(self):
        """Test that when the send fails we try again later."""
        self._set_sending(True)
        result = self._call_sender_one_crash(send_success=False)
        if not result['send_attempt'] or result['send_success']:
            raise error.TestError('Did not properly cause a send failure')
        if result['rate_count'] != 1:
            raise error.TestFail('Did not count a failed send against rate '
                                 'limiting')
        if not result['report_exists']:
            raise error.TestFail('Expected minidump to be saved for later '
                                 'sending')


    def _test_sender_leaves_core_files(self):
        """Test that a core file is left in the send directory.

        Core files will only persist for developer/testing images.  We
        should never remove such a file."""
        self._set_sending(True)
        # Call prepare function to make sure the directory exists.
        core_name = 'something.ending.with.core'
        core_path = self.create_fake_crash_dir_entry(core_name)
        result = self._call_sender_one_crash()
        if not 'Ignoring core file.' in result['output']:
            raise error.TestFail('Expected ignoring core file message')
        if not os.path.exists(core_path):
            raise error.TestFail('Core file was removed')


    def _test_sender_unknown_report_kind(self):
        self._set_sending(True)
        bad_report = self.create_fake_crash_dir_entry('fake.bad')
        result = self._call_sender_one_crash(report=bad_report)
        if (result['report_exists'] or
            result['rate_count'] != 0 or
            result['send_attempt'] or
            result['send_success'] or
            not 'Unknown report' in result['output']):
            raise error.TestFail('Error handling of unknown report kind failed')


    def _test_cron_runs(self):
        """Test sender runs successfully as part of the hourly cron job.

        Assuming we've run test_sender_simple which shows that a minidump
        gets removed as part of sending, we run the cron job (which is
        asynchronous) and wait for that file to be removed to just verify
        the job eventually runs the sender."""
        self._set_sending(True)
        minidump = self._prepare_sender_one_crash(send_success=True,
                                                  reports_enabled=True,
                                                  username='root',
                                                  report=None)
        if not os.path.exists(minidump):
            raise error.TestError('minidump not created')
        utils.system(_CRASH_SENDER_CRON_PATH)
        self._log_reader.set_start_by_current()
        site_utils.poll_for_condition(
            lambda: not os.path.exists(minidump),
            desc='minidump to be removed')
        crash_sender_log = self._log_reader.get_logs()
        logging.debug('Contents of crash sender log: ' + crash_sender_log)
        result = self._parse_sender_output(crash_sender_log)
        if not result['send_attempt'] or not result['send_success']:
            raise error.TestFail('Cron simple run test failed')


    def run_once(self):
        self.run_crash_tests([
            'sender_simple_minidump',
            'sender_simple_kernel_crash',
            'sender_pausing',
            'sender_reports_disabled',
            'sender_rate_limiting',
            'sender_single_instance',
            'sender_send_fails',
            'sender_leaves_core_files',
            'sender_unknown_report_kind',
            'cron_runs'])
