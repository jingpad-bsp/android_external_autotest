# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, subprocess
from signal import SIGSEGV
from autotest_lib.client.bin import site_log_reader, site_utils, test
from autotest_lib.client.common_lib import error, utils

_CRASH_REPORTER_PATH = '/sbin/crash_reporter'
_CRASH_SENDER_PATH = '/sbin/crash_sender'
_CRASH_SENDER_CRON_PATH = '/etc/cron.hourly/crash_sender.hourly'
_CRASH_SENDER_RATE_DIR = '/var/lib/crash_sender'
_CRASH_SENDER_RUN_PATH = '/var/run/crash_sender.pid'
_CORE_PATTERN = '/proc/sys/kernel/core_pattern'
_DAILY_RATE_LIMIT = 8
_MIN_UNIQUE_TIMES = 4
_MOCK_CRASH_SENDING = '/tmp/mock-crash-sending'
_PAUSE_FILE = '/tmp/pause-crash-sending'
_SECONDS_SEND_SPREAD = 3600
_SYSTEM_CRASH_DIR = '/var/spool/crash'
_USER_CRASH_DIR = '/home/chronos/user/crash'


class logging_UserCrash(test.test):
    version = 1


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean all')


    def _set_sending(self, is_enabled):
        if is_enabled:
            if os.path.exists(_PAUSE_FILE):
                os.remove(_PAUSE_FILE)
        else:
            utils.system('touch ' + _PAUSE_FILE)


    def _reset_rate_limiting(self):
        utils.system('rm -rf ' + _CRASH_SENDER_RATE_DIR)


    def _clear_spooled_crashes(self):
        utils.system('rm -rf ' + _SYSTEM_CRASH_DIR)
        utils.system('rm -rf ' + _USER_CRASH_DIR)


    def _kill_running_sender(self):
        if not os.path.exists(_CRASH_SENDER_RUN_PATH):
            return
        running_pid = int(utils.read_file(_CRASH_SENDER_RUN_PATH))
        logging.warning('Detected running crash sender (%d), killing' %
                        running_pid)
        utils.system('kill -9 %d' % running_pid)
        os.remove(_CRASH_SENDER_RUN_PATH)


    def _set_sending_mock(self, mock_enabled, send_success=True):
        if mock_enabled:
            if send_success:
                data = ''
            else:
                data = '1'
            utils.open_write_close(_MOCK_CRASH_SENDING, data)
        else:
            utils.system('rm -f ' + _MOCK_CRASH_SENDING)


    def _get_crash_spool_dir(self, username):
        if username == 'chronos':
            return _USER_CRASH_DIR
        else:
            return _SYSTEM_CRASH_DIR


    def _initialize_crash_reporter(self):
        utils.system('%s --init --nounclean_check' % _CRASH_REPORTER_PATH)


    def initialize(self):
        test.test.initialize(self)
        self._log_reader = site_log_reader.LogReader()


    def cleanup(self):
        self._reset_rate_limiting()
        self._clear_spooled_crashes()
        test.test.cleanup(self)


    def _prepare_sender_one_crash(self, send_success, username, minidump):
        self._set_sending_mock(mock_enabled=True, send_success=send_success)
        if minidump is None:
            minidump = os.path.join(_SYSTEM_CRASH_DIR, 'fake.dmp')
            if not os.path.exists(_SYSTEM_CRASH_DIR):
                os.makedirs(_SYSTEM_CRASH_DIR)
            utils.system('touch ' + minidump)
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


    def _call_sender_one_crash(self, send_success=True, username='root',
                               minidump=None):
        """Call the crash sender script to mock upload one crash.

        Args:
          send_success: Mock a successful send if true
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
                                                  username,
                                                  minidump)
        self._log_reader.set_start_by_current()
        utils.system(_CRASH_SENDER_PATH, ignore_status=True)
        output = self._log_reader.get_logs()
        logging.debug('Crash sender message output:\n' + output)

        if os.path.exists(minidump):
            minidump_exists = True
            os.remove(minidump)
        else:
            minidump_exists = False
        if os.path.exists(_CRASH_SENDER_RATE_DIR):
            rate_count = len(os.listdir(_CRASH_SENDER_RATE_DIR))
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


    def _test_reporter_startup(self):
        """Test that the core_pattern is set up by crash reporter."""
        output = utils.read_file(_CORE_PATTERN).rstrip()
        expected_core_pattern = ('|%s --signal=%%s --pid=%%p --exec=%%e' %
                                 _CRASH_REPORTER_PATH)
        if output != expected_core_pattern:
            raise error.TestFail('core pattern should have been %s, not %s' %
                                 (expected_core_pattern, output))

        self._log_reader.set_start_by_reboot(-1)

        if not self._log_reader.can_find('Enabling crash handling'):
            raise error.TestFail(
                'user space crash handling was not started during last boot')


    def _test_reporter_shutdown(self):
        """Test the crash_reporter shutdown code works."""
        self._log_reader.set_start_by_current()
        utils.system('%s --clean_shutdown' % _CRASH_REPORTER_PATH)
        output = utils.read_file(_CORE_PATTERN).rstrip()
        if output != 'core':
            raise error.TestFail('core pattern should have been core, not %s' %
                                 output)


    def _test_sender_simple(self):
        """Test sending a single crash."""
        self._set_sending(True)
        result = self._call_sender_one_crash()
        if (result['minidump_exists'] or
            result['rate_count'] != 1 or
            not result['send_attempt'] or
            not result['send_success'] or
            result['sleep_time'] < 0 or
            result['sleep_time'] >= _SECONDS_SEND_SPREAD):
            raise error.TestFail('Simple send failed')


    def _test_sender_pausing(self):
        """Test the sender returns immediately when the pause file is present.

        This is testing the sender's test functionality - if this regresses,
        other tests can become flaky because the cron-started sender may run
        asynchronously to these tests."""
        self._set_sending(False)
        result = self._call_sender_one_crash()
        if (not result['minidump_exists'] or
            not 'Exiting early due to' in result['output'] or
            result['send_attempt']):
            raise error.TestFail('Sender did not pause')


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
        if (not result['minidump_exists'] or
            not 'Cannot send more crashes' in result['output'] or
            result['rate_count'] != _DAILY_RATE_LIMIT):
            raise error.TestFail('Crash rate limiting did not take effect')

        # Set one rate file a day earlier and verify can send
        rate_files = os.listdir(_CRASH_SENDER_RATE_DIR)
        rate_path = os.path.join(_CRASH_SENDER_RATE_DIR, rate_files[0])
        statinfo = os.stat(rate_path)
        os.utime(rate_path, (statinfo.st_atime,
                             statinfo.st_mtime - (60 * 60 * 25)))
        utils.system('ls -l ' + _CRASH_SENDER_RATE_DIR)
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
        utils.open_write_close(_CRASH_SENDER_RUN_PATH, str(os.getpid()))
        result = self._call_sender_one_crash()
        if (not 'Already running.' in result['output'] or
            result['send_attempt'] or not result['minidump_exists']):
            raise error.TestFail('Allowed multiple instances to run')
        os.remove(_CRASH_SENDER_RUN_PATH)


    def _test_sender_send_fails(self):
        """Test that when the send fails we try again later."""
        self._set_sending(True)
        result = self._call_sender_one_crash(send_success=False)
        if not result['send_attempt'] or result['send_success']:
            raise error.TestError('Did not properly cause a send failure')
        if result['rate_count'] != 1:
            raise error.TestFail('Did not count a failed send against rate '
                                 'limiting')
        if not result['minidump_exists']:
            raise error.TestFail('Expected minidump to be saved for later '
                                 'sending')


    def _test_cron_runs(self):
        """Test sender runs successfully as part of the hourly cron job.

        Assuming we've run test_sender_simple which shows that a minidump
        gets removed as part of sending, we run the cron job (which is
        asynchronous) and wait for that file to be removed to just verify
        the job eventually runs the sender."""
        self._set_sending(True)
        minidump = self._prepare_sender_one_crash(send_success=True,
                                                  username='root',
                                                  minidump=None)
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


    def _prepare_crasher(self):
        """Extract the crasher and set its permissions.

        crasher is only gzipped to subvert Portage stripping.
        """
        self._crasher_path = os.path.join(self.srcdir, 'crasher')
        utils.system('zcat %s > %s' %
                     (os.path.join(self.srcdir, 'crasher.gz'),
                      self._crasher_path))
        utils.system('chmod 755 %s' % self._crasher_path)


    def _populate_symbols(self):
        """Set up Breakpad's symbol structure.

        Breakpad's minidump processor expects symbols to be in a directory
        hierarchy:
          <symbol-root>/<module_name>/<file_id>/<module_name>.sym
        """
        # Dump the symbols from the crasher
        utils.system('/usr/bin/dump_syms %s > crasher.sym' % self._crasher_path)
        self._symbol_dir = os.path.join(self.srcdir, 'symbols')
        utils.system('rm -rf %s' % self._symbol_dir)
        os.mkdir(self._symbol_dir)
        symbols = utils.read_file('crasher.sym')
        # First line should be:
        # MODULE Linux x86 7BC3323FBDBA2002601FA5BA3186D6540 crasher
        #  or
        # MODULE Linux arm C2FE4895B203D87DD4D9227D5209F7890 crasher
        first_line = symbols.split('\n')[0]
        tokens = first_line.split()
        if tokens[0] != 'MODULE' or tokens[1] != 'Linux':
            raise error.TestError('Unexpected symbols format: %s', first_line)
        file_id = tokens[3]
        target_dir = os.path.join(self._symbol_dir, 'crasher', file_id)
        os.makedirs(target_dir)
        os.rename('crasher.sym', '%s/crasher.sym' % target_dir)


    def _verify_stack(self, stack):
        logging.debug('Crash stackwalk was: %s' % stack)

        # Should identify cause as SIGSEGV at address 0x16
        match = re.search(r'Crash reason:\s+(.*)', stack)
        if not match or match.group(1) != 'SIGSEGV':
            raise error.TestFail('Did not identify SIGSEGV cause')
        match = re.search(r'Crash address:\s+(.*)', stack)
        if not match or match.group(1) != '0x16':
            raise error.TestFail('Did not identify crash address 0x16')

        # Should identify crash at *(char*)0x16 assignment line
        if not ' 0  crasher!recbomb [bomb.cc : 9 ' in stack:
            raise error.TestFail('Did not show crash line on stack')

        # Should identify recursion line which is on the stack
        # for 15 levels
        if not '15  crasher!recbomb [bomb.cc : 12 ' in stack:
            raise error.TestFail('Did not show recursion line on stack')

        # Should identify main line
        if not '16  crasher!main [crasher.cc : 21 ' in stack:
            raise error.TestFail('Did not show main on stack')


    def _run_crasher_process(self, username, extra_args=[]):
        """Runs the crasher process.

        Args:
          username: runs as given user
          extra_args: additional parameters to pass to crasher process

        Returns:
          A dictionary with keys:
            returncode: return code of the crasher
            crashed: did the crasher return segv error code
            crash_reporter_caught: did crash_reporter catch a segv
            output: stderr/stdout output of the crasher process
        """
        self._prepare_crasher()
        self._populate_symbols()

        if username != 'root':
            crasher_command = ['su', username, '-c']
            expected_result = 128 + SIGSEGV
        else:
            crasher_command = []
            expected_result = -SIGSEGV

        crasher_command.append(self._crasher_path)
        crasher_command.extend(extra_args)
        crasher = subprocess.Popen(crasher_command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        output = crasher.communicate()[1]
        logging.debug('Output from %s: %s' % (crasher_command, output))

        # Grab the pid from the process output.  We can't just use
        # crasher.pid unfortunately because that may be the PID of su.
        match = re.search(r'pid=(\d+)', output)
        if not match:
            raise error.TestFail('Could not find pid output from crasher: %s' %
                                 output)
        pid = int(match.group(1))

        expected_message = ('Received crash notification for '
                            'crasher[%d] sig 11' % pid)
        crash_reporter_caught = self._log_reader.can_find(expected_message)

        result = {'crashed': crasher.returncode == expected_result,
                  'crash_reporter_caught': crash_reporter_caught,
                  'output': output,
                  'returncode': crasher.returncode}
        logging.debug('Crasher process result: %s' % result)
        return result


    def _check_crashing_process(self, username):
        self._log_reader.set_start_by_current()

        result = self._run_crasher_process(username)

        if not result['crashed']:
            raise error.TestFail('crasher did not do its job of crashing: %d' %
                                 result['returncode'])

        if not result['crash_reporter_caught']:
            logging.debug('Messages that should have included segv: %s' %
                          self._log_reader.get_logs())
            raise error.TestFail('Did not find segv message: %s' %
                                 expected_message)

        minidump_dir = self._get_crash_spool_dir(username)
        minidumps = os.listdir(minidump_dir)
        if len(minidumps) > 1:
            raise error.TestFail('Too many minidumps written')

        # Now stackwalk the minidump
        minidump_path = os.path.join(minidump_dir, minidumps[0])
        stack = utils.system_output('/usr/bin/minidump_stackwalk %s %s' %
                                    (minidump_path, self._symbol_dir))
        self._verify_stack(stack)

        # Now check that the sending works
        self._set_sending(True)
        result = self._call_sender_one_crash(username=username,
                                             minidump=minidumps[0])
        if (not result['send_attempt'] or not result['send_success'] or
            result['minidump_exists']):
            raise error.TestFail('Minidump not sent properly')
        if not self._crasher_path in result['output']:
            raise error.TestFail('Log did not contain crashing executable name')


    def _test_no_crash(self):
        """Test a program linked against libcrash_dumper can exit normally."""
        self._log_reader.set_start_by_current()
        result = self._run_crasher_process(username='root',
                                           extra_args=['--nocrash'])
        if (result['crashed'] or
            result['crash_reporter_caught'] or
            result['returncode'] != 0):
            raise error.TestFail('Normal exit of program with dumper failed')


    def _test_chronos_crasher(self):
        """Test a user space crash when running as chronos is handled."""
        self._check_crashing_process('chronos')


    def _test_root_crasher(self):
        """Test a user space crash when running as root is handled."""
        self._check_crashing_process('root')


    def run_once(self):
        test_names = [
            'reporter_startup',
            'reporter_shutdown',
            'sender_simple',
            'sender_pausing',
            'sender_rate_limiting',
            'sender_single_instance',
            'sender_send_fails',
            'cron_runs',
            'no_crash',
            'chronos_crasher',
            'root_crasher',
            ]

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
            self._set_sending(True)
            self._set_sending_mock(mock_enabled=False)
