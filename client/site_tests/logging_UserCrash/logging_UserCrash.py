# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import grp, logging, os, pwd, re, stat, subprocess
from signal import SIGSEGV
from autotest_lib.client.bin import site_crash_test, site_utils, test
from autotest_lib.client.common_lib import error, utils

_CORE_PATTERN = '/proc/sys/kernel/core_pattern'
_LEAVE_CORE_PATH = '/root/.leave_core'


class logging_UserCrash(site_crash_test.CrashTest):
    version = 1


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean all')


    def _test_reporter_startup(self):
        """Test that the core_pattern is set up by crash reporter."""
        output = utils.read_file(_CORE_PATTERN).rstrip()
        expected_core_pattern = ('|%s --signal=%%s --pid=%%p' %
                                 self._CRASH_REPORTER_PATH)
        if output != expected_core_pattern:
            raise error.TestFail('core pattern should have been %s, not %s' %
                                 (expected_core_pattern, output))

        self._log_reader.set_start_by_reboot(-1)

        if not self._log_reader.can_find('Enabling user crash handling'):
            raise error.TestFail(
                'user space crash handling was not started during last boot')


    def _test_reporter_shutdown(self):
        """Test the crash_reporter shutdown code works."""
        self._log_reader.set_start_by_current()
        utils.system('%s --clean_shutdown' % self._CRASH_REPORTER_PATH)
        output = utils.read_file(_CORE_PATTERN).rstrip()
        if output != 'core':
            raise error.TestFail('core pattern should have been core, not %s' %
                                 output)


    def _prepare_crasher(self):
        """Extract the crasher and set its permissions.

        crasher is only gzipped to subvert Portage stripping.
        """
        self._crasher_path = {
            True: os.path.join(self.srcdir, 'crasher_breakpad'),
            False: os.path.join(self.srcdir, 'crasher_nobreakpad')
            }
        utils.system('cd %s; tar xzf crasher.tgz' %
                     self.srcdir)


    def _populate_symbols(self):
        """Set up Breakpad's symbol structure.

        Breakpad's minidump processor expects symbols to be in a directory
        hierarchy:
          <symbol-root>/<module_name>/<file_id>/<module_name>.sym
        """
        # Dump the symbols from the crasher
        self._symbol_dir = os.path.join(self.srcdir, 'symbols')
        utils.system('rm -rf %s' % self._symbol_dir)
        os.mkdir(self._symbol_dir)

        for with_breakpad in [True, False]:
            basename = os.path.basename(self._crasher_path[with_breakpad])
            utils.system('/usr/bin/dump_syms %s > %s.sym' %
                         (self._crasher_path[with_breakpad],
                          basename))
            sym_name = '%s.sym' % basename
            symbols = utils.read_file(sym_name)
            # First line should be like:
            # MODULE Linux x86 7BC3323FBDBA2002601FA5BA3186D6540 crasher_XXX
            #  or
            # MODULE Linux arm C2FE4895B203D87DD4D9227D5209F7890 crasher_XXX
            first_line = symbols.split('\n')[0]
            tokens = first_line.split()
            if tokens[0] != 'MODULE' or tokens[1] != 'Linux':
                raise error.TestError('Unexpected symbols format: %s',
                                      first_line)
            file_id = tokens[3]
            target_dir = os.path.join(self._symbol_dir, basename, file_id)
            os.makedirs(target_dir)
            os.rename(sym_name, os.path.join(target_dir, sym_name))


    def _verify_stack(self, stack, basename, from_crash_reporter):
        logging.debug('Crash stackwalk was: %s' % stack)

        # Should identify cause as SIGSEGV at address 0x16
        match = re.search(r'Crash reason:\s+(.*)', stack)
        expected_address = '0x16'
        if from_crash_reporter:
            # We cannot yet determine the crash address when coming
            # through core files via crash_reporter.
            expected_address = '0x0'
        if not match or match.group(1) != 'SIGSEGV':
            raise error.TestFail('Did not identify SIGSEGV cause')
        match = re.search(r'Crash address:\s+(.*)', stack)
        if not match or match.group(1) != expected_address:
            raise error.TestFail('Did not identify crash address %s' %
                                 expected_address)

        # Should identify crash at *(char*)0x16 assignment line
        if not (' 0  %s!recbomb(int) [bomb.cc : 9 ' % basename) in stack:
            raise error.TestFail('Did not show crash line on stack')

        # Should identify recursion line which is on the stack
        # for 15 levels
        if not ('15  %s!recbomb(int) [bomb.cc : 12 ' % basename) in stack:
            raise error.TestFail('Did not show recursion line on stack')

        # Should identify main line
        if not ('16  %s!main [crasher.cc : 21 ' % basename) in stack:
            raise error.TestFail('Did not show main on stack')


    def _run_crasher_process(self, username, with_breakpad, cause_crash=True):
        """Runs the crasher process.

        Args:
          username: runs as given user
          with_breakpad: run crasher that has breakpad (-lcrash) linked in
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

        crasher_command.append(self._crasher_path[with_breakpad])
        basename = os.path.basename(self._crasher_path[with_breakpad])
        if not cause_crash:
            crasher_command.append('--nocrash')
        crasher = subprocess.Popen(crasher_command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        output = crasher.communicate()[1]
        logging.debug('Output from %s: %s' %
                      (self._crasher_path[with_breakpad], output))

        # Grab the pid from the process output.  We can't just use
        # crasher.pid unfortunately because that may be the PID of su.
        match = re.search(r'pid=(\d+)', output)
        if not match:
            raise error.TestFail('Could not find pid output from crasher: %s' %
                                 output)
        pid = int(match.group(1))

        expected_message = ('Received crash notification for '
                            '%s[%d] sig 11' % (basename, pid))

        # Wait until no crash_reporter is running.
        site_utils.poll_for_condition(
            lambda: utils.system('pgrep crash_reporter',
                                 ignore_status=True) != 0,
            timeout=10,
            exception=error.TestError(
              'Timeout waiting for crash_reporter to finish: ' +
              self._log_reader.get_logs()))

        crash_reporter_caught = self._log_reader.can_find(expected_message)

        result = {'crashed': crasher.returncode == expected_result,
                  'crash_reporter_caught': crash_reporter_caught,
                  'output': output,
                  'returncode': crasher.returncode}
        logging.debug('Crasher process result: %s' % result)
        return result


    def _check_crash_directory_permissions(self, crash_dir):
        stat_info = os.stat(crash_dir)
        user = pwd.getpwuid(stat_info.st_uid)[0]
        group = grp.getgrgid(stat_info.st_gid)[0]
        mode = stat.S_IMODE(stat_info.st_mode)

        if crash_dir == '/var/spool/crash':
            expected_user = 'root'
            expected_group = 'root'
            expected_mode = 01755
        else:
            expected_user = 'chronos'
            expected_group = 'chronos'
            expected_mode = 0755

        if user != expected_user or group != expected_group:
            raise error.TestFail(
                'Expected %s.%s ownership of %s (actual %s.%s)' %
                (expected_user, expected_group, crash_dir, user, group))
        if mode != expected_mode:
            raise error.TestFail(
                'Expected %s to have mode %o (actual %o)' %
                (crash_dir, expected_mode, mode))


    def _check_minidump_stackwalk(self, minidump_path, basename,
                                  from_crash_reporter):
        # Now stackwalk the minidump
        stack = utils.system_output('/usr/bin/minidump_stackwalk %s %s' %
                                    (minidump_path, self._symbol_dir))
        self._verify_stack(stack, basename, from_crash_reporter)


    def _check_generated_minidump_sending(self, minidump_path,
                                          username, crasher_basename,
                                          will_syslog_give_name):
        # Now check that the sending works
        self._set_sending(True)
        result = self._call_sender_one_crash(
            username=username,
            report=os.path.basename(minidump_path))
        if (not result['send_attempt'] or not result['send_success'] or
            result['report_exists']):
            raise error.TestFail('Minidump not sent properly')
        if will_syslog_give_name:
            if result['exec_name'] != crasher_basename:
                raise error.TestFail('Executable name incorrect')
        if result['report_kind'] != 'minidump':
            raise error.TestFail('Expected a minidump report')
        if result['report_name'] != minidump_path:
            raise error.TestFail('Sent the wrong minidump report')


    def _check_crashing_process(self, username, with_breakpad):
        self._log_reader.set_start_by_current()

        result = self._run_crasher_process(username, with_breakpad)

        if not result['crashed']:
            raise error.TestFail('crasher did not do its job of crashing: %d' %
                                 result['returncode'])

        if not result['crash_reporter_caught']:
            logging.debug('Messages that should have included segv: %s' %
                          self._log_reader.get_logs())
            raise error.TestFail('Did not find segv message')

        crash_dir = self._get_crash_dir(username)
        crash_contents = os.listdir(crash_dir)
        basename = os.path.basename(self._crasher_path[with_breakpad])

        breakpad_minidump = None
        crash_reporter_minidump = None

        self._check_crash_directory_permissions(crash_dir)

        logging.debug('Contents in %s: %s' % (crash_dir, crash_contents))

        for filename in crash_contents:
            if filename.endswith('.core'):
                # Ignore core files.  We'll test them later.
                pass
            elif filename.startswith(basename):
                # This appears to be a minidump created by the crash reporter.
                if not crash_reporter_minidump is None:
                    raise error.TestFail('Crash reporter wrote multiple '
                                         'minidumps')
                crash_reporter_minidump = os.path.join(crash_dir, filename)
            else:
                # This appears to be a breakpad created minidump.
                if not breakpad_minidump is None:
                    raise error.TestFail('Breakpad wrote multimpe minidumps')
                breakpad_minidump = os.path.join(crash_dir, filename)

        if with_breakpad and not breakpad_minidump:
            raise error.TestFail('%s did not generate breakpad minidump' %
                                 basename)

        if not with_breakpad and breakpad_minidump:
            raise error.TestFail('%s did generate breakpad minidump' % basename)

        if not crash_reporter_minidump:
            raise error.TestFail('crash reporter did not generate minidump')

        if not self._log_reader.can_find('Stored minidump to ' +
                                         crash_reporter_minidump):
            raise error.TestFail('crash reporter did not announce minidump')

        # By default test sending the crash_reporter minidump unless there
        # is a breakpad minidump, and then we test sending it instead.
        send_minidump = crash_reporter_minidump

        if crash_reporter_minidump:
            self._check_minidump_stackwalk(crash_reporter_minidump,
                                           basename,
                                           from_crash_reporter=True)
            will_syslog_give_name = True

        if breakpad_minidump:
            self._check_minidump_stackwalk(breakpad_minidump,
                                           basename,
                                           from_crash_reporter=False)
            send_minidump = breakpad_minidump
            os.unlink(crash_reporter_minidump)
            # If you link against -lcrash, upon sending the syslog will
            # just say exec_name: <very-long-guid>, where that GUID is the
            # GUID generated during breakpad.  Since -lcrash is going away,
            # it seems ok to have the syslog be a little more opaque for
            # these crashes.  They'll be next to sends for the real crash
            # anyway.
            will_syslog_give_name = False

        self._check_generated_minidump_sending(send_minidump,
                                               username,
                                               basename,
                                               will_syslog_give_name)

    def _test_no_crash(self):
        """Test a program linked against libcrash_dumper can exit normally."""
        self._log_reader.set_start_by_current()
        result = self._run_crasher_process(username='root',
                                           with_breakpad=True,
                                           cause_crash=False)
        if (result['crashed'] or
            result['crash_reporter_caught'] or
            result['returncode'] != 0):
            raise error.TestFail('Normal exit of program with dumper failed')


    def _test_chronos_breakpad_crasher(self):
        """Test a user space crash when running as chronos is handled."""
        self._check_crashing_process('chronos', True)


    def _test_chronos_nobreakpad_crasher(self):
        """Test a user space crash when running as chronos is handled."""
        self._check_crashing_process('chronos', False)


    def _test_root_breakpad_crasher(self):
        """Test a user space crash when running as root is handled."""
        self._check_crashing_process('root', True)


    def _test_root_nobreakpad_crasher(self):
        """Test a user space crash when running as root is handled."""
        self._check_crashing_process('root', False)


    def _check_core_file_persisting(self, expect_persist):
        self._log_reader.set_start_by_current()

        result = self._run_crasher_process('root', with_breakpad=False)

        if not result['crashed']:
            raise error.TestFail('crasher did not crash')

        crash_contents = os.listdir(self._get_crash_dir('root'))

        logging.debug('Contents of crash directory: %s', crash_contents)
        logging.debug('Log messages: %s' % self._log_reader.get_logs())

        if expect_persist:
            if not self._log_reader.can_find('Leaving core file at'):
                raise error.TestFail('Missing log message')
            expected_core_files = 1
        else:
            if self._log_reader.can_find('Leaving core file at'):
                raise error.TestFail('Unexpected log message')
            expected_core_files = 0

        dmp_files = 0
        core_files = 0
        for filename in crash_contents:
            if filename.endswith('.dmp'):
                dmp_files += 1
            if filename.endswith('.core'):
                core_files += 1

        if dmp_files != 1:
            raise error.TestFail('Should have been exactly 1 dmp file')
        if core_files != expected_core_files:
            raise error.TestFail('Should have been exactly %d core files' %
                                 expected_core_files)


    def _test_core_file_persists_in_debug(self):
        """Test that a core file persists for development/test builds."""
        if not os.path.exists(_LEAVE_CORE_PATH):
            raise error.TestFail('%s does not exist' % _LEAVE_CORE_PATH)
        self._check_core_file_persisting(True)


    def _test_core_file_removed_in_production(self):
        """Test that core files do not stick around for production builds."""
        # Avoid remounting / rw by instead creating a tmpfs in /root and
        # populating it with everything but the
        utils.system('tar -cvz -C /root -f /tmp/root.tgz .')
        utils.system('mount -t tmpfs tmpfs /root')
        try:
            utils.system('tar -xvz -C /root -f /tmp/root.tgz .')
            os.remove(_LEAVE_CORE_PATH)
            if os.path.exists(_LEAVE_CORE_PATH):
                raise error.TestFail('.leave_core file did not disappear')
            self._check_core_file_persisting(False)
        finally:
            os.system('umount /root')


    # TODO(kmixter): Test crashing a process as ntp or some other
    # non-root, non-chronos user.

    def run_once(self):
        self.run_crash_tests(['reporter_startup',
                              'reporter_shutdown',
                              'no_crash',
                              'chronos_breakpad_crasher',
                              'chronos_nobreakpad_crasher',
                              'root_breakpad_crasher',
                              'root_nobreakpad_crasher',
                              'core_file_persists_in_debug',
                              'core_file_removed_in_production'],
                              initialize_crash_reporter = True)
