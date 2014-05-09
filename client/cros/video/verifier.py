# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.cros.video import method_logger


class VideoScreenShotVerifier(object):
    """
    Verifies that received screenshots are same as expected.

    This class relies on a provided image comparer to decide if two images are
    one and the same.

    """


    @method_logger.log
    def __init__(self, image_comparer, wait_time_btwn_verifications):
        """
        Initializes the verifier.

        @param image_comparer: object, image comparer to use.
        @param wait_time_btwn_verifications: time to wait between two successive
                                             calls to compare two images.

        """
        self.image_comparer = image_comparer
        self.wait_time_btwn_verifications = wait_time_btwn_verifications


    @method_logger.log
    def verify(self, golden_images, test_images):
        """
        Verifies that two sets of images are the same using provided comparer.

        @param golden_images: list of complete paths to golden images.
        @param test_images: list of complete paths to test images.

        @returns a list of dictionaries of test results for each comparison.

        """
        with self.image_comparer as comparer:
            test_results = []
            for golden_image, test_image in zip(golden_images, test_images):
                upload_res = comparer.compare(golden_image, test_image)
                logging.debug('**Upload Results:**')
                logging.debug(upload_res)
                test_results.append(upload_res)
                time.sleep(self.wait_time_btwn_verifications)

        return test_results


