# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from autotest_lib.client.common_lib import time_utils


class time_utils_unittest(unittest.TestCase):
    """Unittest for time_utils function."""

    TIME_STRING = "2014-08-20 14:23:56"
    TIME_SECONDS = 1408569836
    TIME_OBJ = datetime.datetime(year=2014, month=8, day=20, hour=14,
                                 minute=23, second=56)

    def test_epoch_time_to_date_string(self):
        """Test function epoch_time_to_date_string."""
        time_string = time_utils.epoch_time_to_date_string(self.TIME_SECONDS)
        self.assertEqual(self.TIME_STRING, time_string)


    def test_to_epoch_time_success(self):
        """Test function to_epoch_time."""
        self.assertEqual(self.TIME_SECONDS,
                         time_utils.to_epoch_time(self.TIME_STRING))

        self.assertEqual(self.TIME_SECONDS,
                         time_utils.to_epoch_time(self.TIME_OBJ))


if __name__ == '__main__':
    unittest.main()