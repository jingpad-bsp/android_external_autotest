# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, string, time, utils, os, subprocess
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_logging, cros_ui_test
import pprint

class platform_TrackpadStress(test.test):
    version = 1


    def run_once(self, verify_only=False):
        log_reader = cros_logging.LogReader(include_rotated_logs=False)
        log_reader.set_start_by_reboot(-1)

        # Verify the synaptics kernel driver successfully probed the trackpad
        check_string = 'Synaptics Touchpad, model: 1, fw:'
        if not log_reader.can_find(check_string):
            raise error.TestFail('Pre-check 1: Unable to locate trackpad '
                                 'logging string: %s' % check_string)

        for line in log_reader.read_all_logs(start=log_reader._start_line):
            if line.find(check_string) != -1 and line.find('0x0/0x0') == 0:
                # If 0x0/0x0 exists in the caps string, then this signals that
                # the device is stuck in its bootloader
                raise error.TestFail('Pre-check 1a: It appears the trackpad is '
                                     'stuck in the bootloader.  Complete caps '
                                     'string:\n%s' % caps_string)

        check_string = 'input: SynPS/2 Synaptics TouchPad as'
        if not log_reader.can_find(check_string):
            raise error.TestFail('Pre-check 2: Unable to locate trackpad '
                                 'logging string: %s' % check_string)

        if verify_only:
            self.job.set_state('client_passed', True)
            return

        bpath = os.path.abspath(__file__)
        forever_script = os.path.join(os.path.dirname(bpath), 'forever.py')

        pid_file_path = '/tmp/fork_process_pid.txt'
        if os.path.isfile(pid_file_path) == True:
            os.remove(pid_file_path)
        process = subprocess.Popen(['/usr/local/bin/python', forever_script,
                                    '-f', pid_file_path], shell=False,
                                   env=None)

        logging.info('Waiting for forever script to create pid file.')
        counter = 0
        while (os.path.isfile(pid_file_path) == False and counter < 30):
            time.sleep(1)
            counter = counter + 1
        if os.path.isfile(pid_file_path) == False:
            raise error.TestFail('The forever script did not create a pid file.'
                                 'It must not have started up.  Checking path: '
                                 '%s' % pid_file_path)
        with open(pid_file_path, 'r') as f:
            pid = f.readline()
        try:
            os.kill(int(pid), 0)
        except OSError:
            raise error.TestFail('The forever script process id: %s cannot be '
                                 'found.' % pid.rstrip('\n'))

        self.job.set_state('client_passed', True)

