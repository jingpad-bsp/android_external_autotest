# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import crash_test


_25_HOURS_AGO = -25 * 60 * 60
_CRASH_SENDER_CRON_PATH = '/etc/cron.hourly/crash_sender.hourly'
_DAILY_RATE_LIMIT = 32
_MIN_UNIQUE_TIMES = 4
_SECONDS_SEND_SPREAD = 3600

class logging_CrashSender(crash_test.CrashTest):
    version = 1


    def _check_hardware_info(self, result):
        # Get board name
        lsb_release = utils.read_file('/etc/lsb-release')
        board_match = re.search(r'CHROMEOS_RELEASE_BOARD=(.*)', lsb_release)
        if not ('Board: %s' % board_match.group(1)) in result['output']:
            raise error.TestFail('Missing board name %s in output' %
                                 board_match.group(1))
        # Get hwid
        with os.popen("crossystem hwid 2>/dev/null", "r") as hwid_proc:
            hwclass = hwid_proc.read()
	if not hwclass:
            hwclass = 'undefined'
        if not ('HWClass: %s' % hwclass) in result['output']:
            raise error.TestFail('Expected hwclass %s in output' % hwclass)


    def _check_simple_minidump_send(self, report, log_path=None):
        result = self._call_sender_one_crash(report=report)
        if (result['report_exists'] or
            result['rate_count'] != 1 or
            not result['send_attempt'] or
            not result['send_success'] or
            result['sleep_time'] < 0 or
            result['sleep_time'] >= _SECONDS_SEND_SPREAD or
            result['report_kind'] != 'minidump' or
            result['report_payload'] != '/var/spool/crash/fake.dmp' or
            result['exec_name'] != 'fake' or
            not 'Version: my_ver' in result['output']):
            raise error.TestFail('Simple minidump send failed')
        if log_path and not ('log: @%s' % log_path) in result['output']:
            raise error.TestFail('Minidump send missing log')
        self._check_hardware_info(result)


    def _test_sender_simple_minidump(self):
        """Test sending a single minidump crash report."""
        self._check_simple_minidump_send(None)


    def _test_sender_simple_minidump_with_log(self):
        """Test that a minidump report with an auxiliary log is sent."""
        dmp_path = self.write_crash_dir_entry('fake.dmp', '')
        log_path = self.write_crash_dir_entry('fake.log', '')
        meta_path = self.write_fake_meta('fake.meta', 'fake', dmp_path,
                                         log=log_path)
        self._check_simple_minidump_send(meta_path, log_path)


    def _shift_file_mtime(self, path, delta):
        statinfo = os.stat(path)
        os.utime(path, (statinfo.st_atime,
                        statinfo.st_mtime + delta))


    def _test_sender_simple_old_minidump(self):
        """Test that old minidumps and metadata are sent."""
        dmp_path = self.write_crash_dir_entry('fake.dmp', '')
        meta_path = self.write_fake_meta('fake.meta', 'fake', dmp_path)
        self._shift_file_mtime(dmp_path, _25_HOURS_AGO)
        self._shift_file_mtime(meta_path, _25_HOURS_AGO)
        self._check_simple_minidump_send(meta_path)


    def _test_sender_simple_kernel_crash(self):
        """Test sending a single kcrash report."""
        kcrash_fake_report = self.write_crash_dir_entry(
            'kernel.today.kcrash', '')
        self.write_fake_meta('kernel.today.meta',
                             'kernel',
                             kcrash_fake_report)
        result = self._call_sender_one_crash(report=kcrash_fake_report)
        if (result['report_exists'] or
            result['rate_count'] != 1 or
            not result['send_attempt'] or
            not result['send_success'] or
            result['sleep_time'] < 0 or
            result['sleep_time'] >= _SECONDS_SEND_SPREAD or
            result['report_kind'] != 'kcrash' or
            (result['report_payload'] !=
             '/var/spool/crash/kernel.today.kcrash') or
            result['exec_name'] != 'kernel'):
            raise error.TestFail('Simple kcrash send failed')
        self._check_hardware_info(result)


    def _test_sender_pausing(self):
        """Test the sender returns immediately when the pause file is present.

        This is testing the sender's test functionality - if this regresses,
        other tests can become flaky because the cron-started sender may run
        asynchronously to these tests.  Disable child sending as normally
        this environment configuration allows our children to run in spite of
        the pause file."""
        self._set_system_sending(False)
        self._set_child_sending(False)
        result = self._call_sender_one_crash()
        if (not result['report_exists'] or
            not 'Exiting early due to' in result['output'] or
            result['send_attempt']):
            raise error.TestFail('Sender did not pause')


    def _test_sender_reports_disabled(self):
        """Test that when reporting is disabled, we don't send."""
        result = self._call_sender_one_crash(reports_enabled=False)
        if (result['report_exists'] or
            not 'Uploading is disabled' in result['output'] or
            result['send_attempt']):
            raise error.TestFail('Sender did not handle reports disabled')


    def _test_sender_rate_limiting(self):
        """Test the sender properly rate limits and sends with delay."""
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
        self._shift_file_mtime(rate_path, _25_HOURS_AGO)
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
        utils.open_write_close(self._CRASH_SENDER_RUN_PATH, str(os.getpid()))
        result = self._call_sender_one_crash()
        if (not 'Already running.' in result['output'] or
            result['send_attempt'] or not result['report_exists']):
            raise error.TestFail('Allowed multiple instances to run')
        os.remove(self._CRASH_SENDER_RUN_PATH)


    def _test_sender_send_fails(self):
        """Test that when the send fails we try again later."""
        result = self._call_sender_one_crash(send_success=False)
        if not result['send_attempt'] or result['send_success']:
            raise error.TestError('Did not properly cause a send failure')
        if result['rate_count'] != 1:
            raise error.TestFail('Did not count a failed send against rate '
                                 'limiting')
        if not result['report_exists']:
            raise error.TestFail('Expected minidump to be saved for later '
                                 'sending')


    def _test_sender_orphaned_files(self):
        """Test that payload and unknown files that are old are removed."""
        core_file = self.write_crash_dir_entry('random1.core', '')
        unknown_file = self.write_crash_dir_entry('.unknown', '')
        # As new files, we expect crash_sender to leave these alone.
        results = self._call_sender_one_crash()
        if ('Removing old orphaned file' in results['output'] or
            not os.path.exists(core_file) or
            not os.path.exists(unknown_file)):
            raise error.TestFail('New orphaned files were removed')
        self._shift_file_mtime(core_file, _25_HOURS_AGO)
        self._shift_file_mtime(unknown_file, _25_HOURS_AGO)
        results = self._call_sender_one_crash()
        if (not 'Removing old orphaned file' in results['output'] or
            os.path.exists(core_file) or os.path.exists(unknown_file)):
            raise error.TestFail(
                'Old orphaned files were not removed')


    def _test_sender_incomplete_metadata(self):
        """Test that incomplete metadata file is removed once old."""
        dmp_file = self.write_crash_dir_entry('incomplete.dmp', '')
        meta_file = self.write_fake_meta('incomplete.meta',
                                         'unknown',
                                         dmp_file,
                                         complete=False)
        # As new files, we expect crash_sender to leave these alone.
        results = self._call_sender_one_crash()
        if ('Removing recent incomplete report' in results['output'] or
            not os.path.exists(meta_file) or
            not os.path.exists(dmp_file)):
            raise error.TestFail('New unknown files were removed')
        self._shift_file_mtime(meta_file, _25_HOURS_AGO)
        results = self._call_sender_one_crash()
        if (not 'Removing old incomplete metadata' in results['output'] or
            os.path.exists(meta_file) or os.path.exists(dmp_file)):
            raise error.TestFail(
                'Old unknown/incomplete files were not removed')


    def _test_sender_missing_payload(self):
        meta_file = self.write_fake_meta('bad.meta',
                                         'unknown',
                                         'bad.dmp')
        other_file = self.write_crash_dir_entry('bad.other', '')
        results = self._call_sender_one_crash(report=meta_file)
        # Should remove this file.
        if (not 'Missing payload' in results['output'] or
            os.path.exists(meta_file) or
            os.path.exists(other_file)):
            raise error.TestFail('Missing payload case handled wrong')


    def run_once(self):
        self.run_crash_tests([
            'sender_simple_minidump',
            'sender_simple_old_minidump',
            'sender_simple_minidump_with_log',
            'sender_simple_kernel_crash',
            'sender_pausing',
            'sender_reports_disabled',
            'sender_rate_limiting',
            'sender_single_instance',
            'sender_send_fails',
            'sender_orphaned_files',
            'sender_incomplete_metadata',
            'sender_missing_payload']);
