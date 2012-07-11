# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class security_Tpmd(test.test):
    version = 2

    def test_nvram(self):
        SLOT = 0x20000004
        opts = dbus.Dictionary({ 'LockOnce': dbus.Boolean(True, 1) })
        self.nvram_proxy.Allocate(SLOT, 16, opts)
        b = [dbus.Byte(ord(x)) for x in 'Hello, World! AA']
        if self.nvram_proxy.IsLocked(SLOT):
            self.nvram_proxy.Free(SLOT)
            raise error.TestFail('Allocated slot was locked')
        written = dbus.Array(b)
        self.nvram_proxy.Write(SLOT, written)
        if not self.nvram_proxy.IsLocked(SLOT):
            self.nvram_proxy.Free(SLOT)
            raise error.TestFail('Written slot was not locked')
        read = self.nvram_proxy.Read(SLOT)
        if read != written:
            self.nvram_proxy.Free(SLOT)
            raise error.TestFail('read != written: %s != %s' % (read, written))
        self.nvram_proxy.Free(SLOT)

    def test_encrypt(self):
        plaintext = dbus.ByteArray('Hello, World!')
        ciphertext = self.proxy.Encrypt(plaintext)
        recovered = self.proxy.Decrypt(ciphertext, byte_arrays=True)
        if recovered != plaintext:
            raise error.TestFail('recovered != plaintext: %s != %s' %
                                 (recovered, plaintext))

    def test_status(self):
        stat = self.proxy.GetStatus()
        try:
            j = json.loads(stat)
        except ValueError as e:
            raise error.TestFail('GetStatus() gave bogus json: %s' % stat)

    def run_once(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object('org.chromium.tpmd', '/org/chromium/tpmd')
        self.proxy = dbus.Interface(obj, dbus_interface='org.chromium.tpmd')
        self.nvram_proxy = dbus.Interface(obj,
            dbus_interface='org.chromium.tpmd.nvram')
        self.test_encrypt()
        self.test_status()
        self.test_nvram()
