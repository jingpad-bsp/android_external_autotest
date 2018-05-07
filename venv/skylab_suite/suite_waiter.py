# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Waiter for waiting for a CrOS suite in skylab."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


class SuiteResultWaiter(object):
    """Class for a skylab suite results waiter.

    Its basic features include:
        1. Wait for a child test's status in skylab.
    """

    def wait_for_results(self):
        """Wait for child jobs to finish and return their results."""
        return
