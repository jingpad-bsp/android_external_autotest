# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

def missing_firmware_version():
    f = os.popen("crossystem fwid")
    if not f:
        return True
    f.close()
    return False

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

def checkp(space, permission):
    c = "tpmc getp %s" % space
    out = os.popen(c)
    l = out.readline()
    out.close()
    if (not re.match(".*%s" % permission, l)):
        raise error.TestError("invalid response to %s: %s" % (c, l))

class hardware_TPMCheck(test.test):
    version = 1

    def run_once(self):

        if missing_firmware_version():
            logging.warning("no firmware version, skipping test")
            return

        try:
            utils.system("stop tcsd", ignore_status=True)

            # Check volatile (ST_CLEAR) flags
            d = dict_from_command("tpmc getvf");
            expect(d, "deactivated", "0")
            expect(d, "physicalPresence", "0")
            expect(d, "physicalPresenceLock", "1")
            expect(d, "bGlobalLock", "1")

            # Check permanent flags
            d = dict_from_command("tpmc getpf");
            expect(d, "disable", "0")
            expect(d, "ownership", "1")
            expect(d, "deactivated", "0")
            expect(d, "physicalPresenceHWEnable", "0")
            expect(d, "physicalPresenceCMDEnable", "1")
            expect(d, "physicalPresenceLifetimeLock", "1")
            expect(d, "nvLocked", "1")

            # Check space permissions
            checkp("0x1007", "0x8001")
            checkp("0x1008", "0x1")

            # Check kernel space UID
            out = os.popen("tpmc read 0x1008 0x5")
            l = out.readline()
            if (not re.match(".* 4c 57 52 47$", l)):
                raise error.TestError("invalid kernel space UID: %s" % l)
            out.close()

        finally:
            utils.system("start tcsd")
