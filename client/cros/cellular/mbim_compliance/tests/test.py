# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.cros.cellular.mbim_compliance import entity
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class Test(entity.Entity):
    """ Base class for all tests. """

    def run(self):
        """ Run the test. """
        logging.info('-- Test (%s) begin --', self.name())
        result = self.run_internal()
        logging.info('-- Test (%s) end [%s]--',
                     self.name(),
                     'PASS' if result else 'FAIL')
        return result


    def run_internal(self):
        """
        The actual method runs the actual test.
        Subclasses should override this method to run their own test.

        """
        mbim_errors.log_and_raise(NotImplementedError)


    def name(self):
        """
        Return a generic test tag to be used for logging.

        @returns str name.

        """
        return self.__class__.__name__
