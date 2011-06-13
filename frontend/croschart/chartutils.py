# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utility functions.

   Used by >1 module.
"""


import os


FIELD_SEPARATOR = ','


def AbridgeCommonKeyPrefix(test_name, test_keys):
  """Easier to read if common part stripped off keys in legend."""
  new_test_keys = test_keys
  if len(test_keys) > 1:
    common_prefix = os.path.commonprefix(test_keys)
    prefix_len = len(common_prefix)
    if prefix_len > 0:
      new_test_keys = []
      test_name += ' - %s' % common_prefix
      for test_key in test_keys:
        new_test_keys.append(test_key[prefix_len:])
  return test_name, new_test_keys


def GetTestNameKeys(testkey):
  """Helper to retrieve test_name and test_keys from request."""
  test_name_keys = testkey.split(FIELD_SEPARATOR)
  return test_name_keys[0], test_name_keys[1:]
