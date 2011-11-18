# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import commands, logging, os, re, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import rtc, sys_power

#
# It may be useful in the future to combine the following three functions
# into a separate library for use across multiple AutoTest files.
# At present, the AutoTest files listed below use these common functions:
#   * hardware_TPMCheckS3 (this test), and
#   * hardware_TPMCheck
#

def dict_from_command(command):
    dict = {}
    out = os.popen(command)
    for linecr in out.readlines():
        line = linecr.strip()
        match = re.match("([^ ]+) (.*)", line)
        k = match.group(1)
        v = match.group(2)
        dict[k] = v
    out.close()
    return dict

def expect(d, key, value):
    if (d[key] != value):
        raise error.TestError("expecting %s = %s, observing %s = %s" %
                              (key, value, key, d[key]))
    logging.debug("TPM: found %s = %s" % (key, value))

def check_tpm_volatile_states( ):
    # Check TPM state values expected during normal operation, prior to
    #   and after a suspend/resume to/from RAM.
    #
    # Must stop the TCSD process to be able to collect TPM status,
    #   then restart TCSD process to leave system in a known good state.
    try:
        # Stop tcsd daemon to have access to tpmc commands
        utils.system("stop tcsd", ignore_status=True)
        # Check TPM volatile (ST_CLEAR) flags
        d = dict_from_command("tpmc getvf");
        expect(d, "deactivated", "0")
        expect(d, "physicalPresence", "0")
        expect(d, "physicalPresenceLock", "1")
        expect(d, "bGlobalLock", "1")
    finally:
        utils.system("start tcsd")

class hardware_TPMCheckS3(test.test):

    # This test checks for the TPM to be able to Suspend and Resume from
    #   RAM and maintain previous state.
    #
    # The test sequence follows the steps below:
    #   1. Read current TPM values
    #   2. Cause suspend to RAM for 15 seconds
    #   3. Read TPM values after resume from RAM
    #   4. Error if TPM values after resume are not as expected.
    #

    version = 1

    def run_once(self):
        # Some idle time before initiating suspend-to-ram
        # Can tweak idle_time if necessary.  Minimum of zero.
        idle_time = 3
        time.sleep(idle_time)

        # Check for current state of the TPM prior to Suspend to RAM.
        check_tpm_volatile_states()

        # Can tweek time_to_sleep if necessary, but should
        #     be at least 10 seconds or more.
        time_to_sleep = 10

        # Set the alarm
        alarm_time = rtc.get_seconds() + time_to_sleep
        logging.debug('alarm_time = %d', alarm_time)
        rtc.set_wake_alarm(alarm_time)

        # Suspend the system to RAM
        sys_power.suspend_to_ram()

        # Check for current state of the TPM after Resume from RAM.
        check_tpm_volatile_states()
