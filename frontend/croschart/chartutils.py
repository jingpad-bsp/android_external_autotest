# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utility functions.

   Used by >1 module.
"""


FIELD_SEPARATOR = ','


def GetTestNameKeys(testkey):
  """Helper to retrieve test_name and test_keys from request."""
  test_name_keys = testkey.split(FIELD_SEPARATOR)
  return test_name_keys[0], test_name_keys[1:]


