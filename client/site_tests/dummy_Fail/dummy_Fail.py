# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class dummy_Fail(test.test):
    version = 1

    def run_once(self, to_throw=None):
        if to_throw:
            if to_throw == 'TestFail': logging.error('It is an error!')
            raise getattr(error, to_throw)('always fail')
        else:  # Generate a crash to test that behavior.
            self.write_perf_keyval({'perf_key': 102.7})
            self.job.record('WARN', self.tagged_testname,
                            'Received crash notification for sleep[273] sig 6')
