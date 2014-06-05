# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time


from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.cros.video import bp_image_comparer


WORKING_DIR = '/tmp/test'
BIOPIC_PROJECT_NAME = 'chromeos.test.desktopui.systemtray.private'

# TODO: Set up an alias so that anyone can monitor results.
BIOPIC_CONTACT_EMAIL = 'mussa@google.com'
BIOPIC_TIMEOUT_S = 1


class ui_SystemTray(test.test):

    # Comply with autotest requiring 'version' attribute
    version = 2

    def run_once(self, shelf_height, x_offset_in_pixels, y_offset_in_pixels):
        """
        Runs the test.
        """

        file_utils.make_leaf_dir(WORKING_DIR)

        timestamp = time.strftime('%Y_%m_%d_%H%M', time.localtime())

        filename = '%s_%s_%s.png' % (timestamp,
                                     utils.get_current_board(),
                                     utils.get_chromeos_release_version())

        filepath = os.path.join(WORKING_DIR, filename)

        utils.take_screen_shot_crop_by_height(filepath,
                                              shelf_height,
                                              x_offset_in_pixels,
                                              y_offset_in_pixels)

        with bp_image_comparer.BpImageComparer(BIOPIC_PROJECT_NAME,
                                               BIOPIC_CONTACT_EMAIL,
                                               BIOPIC_TIMEOUT_S) as comparer:
            # We just care about storing these images for we can look at them
            # later. We don't wish to compare images right now.
            # Make reference images same as test image!
            comparer.compare(filepath, filepath)

        file_utils.rm_dir_if_exists(WORKING_DIR)



