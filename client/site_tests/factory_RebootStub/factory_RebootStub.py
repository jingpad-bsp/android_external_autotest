# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# factory_test library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import factory_test


class factory_RebootStub(test.test):
    version = 1

    def run_once(self):
        factory_test.XXX_log('factory_RebootStub')
