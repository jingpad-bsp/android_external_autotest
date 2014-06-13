# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.cros.cellular.mbim_compliance import entity
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class Sequence(entity.Entity):
    """ Base class for all sequences. """

    def run(self):
        """ Run the sequence. """
        logging.info('---- Sequence (%s) begin ----', self.name())
        self.run_internal()
        logging.info('---- Sequence (%s) end ----', self.name())


    def run_internal(self):
        """
        The actual method runs the sequence.
        Subclasses should override this method to run their own sequence.

        """
        mbim_errors.log_and_raise(NotImplementedError)


    def name(self):
        """ Return str name. """
        return self.__class__.__name__
