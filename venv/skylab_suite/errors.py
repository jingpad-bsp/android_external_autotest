# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definition of CrOS suite exceptions in skylab."""


class InValidPropertyError(Exception):
    """Raised if a suite's property is not valid."""


class NoAvailableDUTsError(Exception):
    """Raised if there's no available DUTs for provision suite."""
