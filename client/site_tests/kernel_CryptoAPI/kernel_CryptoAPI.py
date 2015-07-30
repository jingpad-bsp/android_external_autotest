#!/usr/bin/python
#
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils


class kernel_CryptoAPI(test.test):
    """
    Verify that the crypto user API can't be used to load arbitrary modules.
    Uses the kernel module 'test_module'
    """
    version = 1
    preserve_srcdir = True

    def initialize(self):
        self.job.require_gcc()


    def setup(self):
        os.chdir(self.srcdir)
        utils.make()


    def try_load_mod(self, module):
        """
        Try to load a (non-crypto) module using the crypto UAPI
        @param module: name of the kernel module to try to load
        """
        if utils.module_is_loaded(module):
            utils.unload_module(module)

        path = os.path.join(self.srcdir, 'crypto_load_mod ')
        utils.system(path + module)

        if utils.module_is_loaded(module):
            utils.unload_module(module)
            raise error.TestFail('Able to load module "%s" using crypto UAPI' %
                                 module)


    def run_once(self):
        # crypto tests only work with AF_ALG support, so run only on >=3.8
        # kernels
        kernel_ver = os.uname()[2]
        if utils.compare_versions(kernel_ver, "3.8") < 0:
            raise error.TestNAError("Crypto tests not run for pre-v3.8 kernels")

        module = "test_module"
        self.try_load_mod(module)
