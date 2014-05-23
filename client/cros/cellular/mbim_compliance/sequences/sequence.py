# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.client.cros.cellular.mbim_compliance import entity
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class Sequence(entity.Entity):
    """ Base class for all sequences. """

    def run(self):
        """ Run the sequence. """
        mbim_errors.log_and_raise(NotImplementedError())
