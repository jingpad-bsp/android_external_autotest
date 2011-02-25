# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import test

_KERN_WARNING = 4

_WHITELIST = [
    "Kernel-defined memdesc doesn't match the one from EFI!",
    "Warning only 1919MB will be used.",
    "Use a HIGHMEM enabled kernel.",
    "pnp 00:01: io resource (0x164e-0x164f) overlaps 0000:00:1c.0 "
    "BAR 7 (0x1000-0x1fff), disabling",
    "i915 0000:00:02.0: Invalid ROM contents",
    "[drm:intel_init_bios] *ERROR* VBT signature missing",
    "usb 1-2: config 1 has an invalid interface number: 1 but max is 0",
    "usb 1-2: config 1 has no interface number 0",
    "device-mapper: verity: Failed to acquire device 'ROOT_DEV': -1",
    "device-mapper: table: 254:0: verity: Device lookup failed",
    "dm: starting dm-0 (vroot) failed",
    "EXT3-fs warning: maximal mount count reached, running e2fsck is "
    "recommended",
    "i2c i2c-2: The new_device interface is still experimental and may change "
    "in a near future",
    "industrialio: module is from the staging directory, "
    "the quality is unknown, you have been warned.",
    "tsl2563: module is from the staging directory, the quality is unknown, "
    "you have been warned.",
]

""" Interesting fields from meminfo that we want to log
    If you add fields here, you must add them to the constraints
    in the control file
"""
_meminfo_fields = { 'MemFree'   : 'coldboot_memfree_mb',
                    'AnonPages' : 'coldboot_anonpages_mb',
                    'Buffers'   : 'coldboot_buffers_mb',
                    'Cached'    : 'coldboot_cached_mb',
                    'Active'    : 'coldboot_active_mb',
                    'Inactive'  : 'coldboot_inactive_mb',
                    }

class kernel_BootMessagesServer(test.test):
    version = 1


    def _read_dmesg(self, filename):
        """Put the contents of 'dmesg -r' into the given file.

        @param filename: The file to write 'dmesg -r' into.
        """
        f = open(filename, 'w')
        self._client.run('dmesg -r', stdout_tee=f)
        f.close()

        return utils.read_file(filename)

    def _reboot_machine(self):
        """Reboot the client machine.

        We'll wait until the client is down, then up again.
        """
        self._client.run('reboot')
        self._client.wait_down()
        self._client.wait_up()

    def _read_meminfo(self, filename):
        """Fetch /proc/meminfo from client and return lines in the file

        @param filename: The file to write 'cat /proc/meminfo' into.
        """

        f = open(filename, 'w')
        self._client.run('cat /proc/meminfo', stdout_tee=f)
        f.close()

        return utils.read_file(filename)

    def _parse_meminfo(self, meminfo, perf_vals):
        """ Parse the contents of each line of meminfo
            if the line matches one of the interesting keys
            save it into perf_vals in terms of megabytes

            @param filelines: list of lines in meminfo
            @param perf_vals: dictionary of performance metrics
        """

        for line in meminfo.splitlines():
            stuff = re.match('(.*):\s+(\d+)', line)
            stat  = stuff.group(1)
            if stat in _meminfo_fields:
                value  = int(stuff.group(2))/ 1024
                metric = _meminfo_fields[stat]
                perf_vals[metric] = value

    def run_once(self, host=None):
        """Run the test.

        @param host: The client machine to connect to; should be a Host object.
        """
        assert host is not None, "The host must be specified."

        self._client = host
        dmesg_filename = os.path.join(self.resultsdir, 'dmesg')
        meminfo_filename = os.path.join(self.resultsdir, 'meminfo')
        perf_vals = {}

        self._reboot_machine()
        meminfo = self._read_meminfo(meminfo_filename)
        self._parse_meminfo(meminfo, perf_vals)
        dmesg = self._read_dmesg(dmesg_filename)
        unexpected = utils.check_raw_dmesg(dmesg, _KERN_WARNING, _WHITELIST)

        if unexpected:
            f = open(os.path.join(self.resultsdir, 'dmesg.err'), 'w')
            for line in unexpected:
                logging.error('UNEXPECTED DMESG: %s' % line)
                f.write('%s\n' % line)
            f.close()
            raise error.TestFail("Unexpected dmesg warnings and/or errors.")

        self.write_perf_keyval(perf_vals)
