# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a stub factory test, run once reboot tests are completed, to
# allow the autotest logs to record success status, and thereby for
# the UI to display that status.


from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory


class factory_RebootStub(test.test):
    version = 1

    def run_once(self):
        factory.log('%s run_once' % self.__class__)
