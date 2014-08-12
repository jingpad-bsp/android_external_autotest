# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.cros.video import method_logger
from autotest_lib.client.common_lib import error


class Verifier(object):
    """
    Verifies that received screenshots are same as expected.

    This class relies on a provided image comparer to decide if two images are
    one and the same.

    Clients who have many images to compare should use this class and pass in
    a comparer of their choice.

    Comparer are just about comparing two images and this class takes over with
    test-related things: logging, deciding pass or fail.

    """


    @method_logger.log
    def __init__(self, image_comparer, stop_on_first_failure, threshold=0):
        """
        @param image_comparer: object, image comparer to use.
        @param stop_on_first_failure: bool, true if the test should be stopped
                                      once a test image doesn't match its ref.
        @param threshold: int, a value which the pixel difference between test
                          image and golden image has to exceed before the
                          doublecheck comparer is used.

        """
        self.image_comparer = image_comparer
        self.stop_on_first_failure = stop_on_first_failure
        self.threshold = threshold


    @method_logger.log
    def verify(self, golden_image_paths, test_image_paths):
        """
        Verifies that two sets of images are the same using provided comparer.

        @param golden_image_paths: list of complete paths to golden images.
        @param test_image_paths: list of complete paths to test images.


        """

        if type(golden_image_paths) is not list:
            golden_image_paths = [golden_image_paths]

        if type(test_image_paths) is not list:
            test_image_paths = [test_image_paths]

        failure_count = 0

        logging.debug("***BEGIN Image Verification***")

        log_msgs = []

        for g_image, t_image in zip(golden_image_paths, test_image_paths):

            with self.image_comparer:
                diff_pixels = self.image_comparer.compare(g_image, t_image)

            log_msg = ("Reference: %s. Test: %s. Pixel diff: %d. Thres.: %d" %
                      (g_image, t_image, diff_pixels, self.threshold))

            logging.debug(log_msg)
            log_msgs.append(log_msg)

            if diff_pixels > self.threshold:
                failure_count += 1

                if self.stop_on_first_failure:
                    raise error.TestError("%s. Bailing out." % log_msg)

        if failure_count > 0:
            cnt = len(golden_image_paths)
            raise error.TestError("%d / %d test images were not golden.%s"
                                  % (failure_count, cnt, log_msgs))

        logging.debug("***All Good.***")