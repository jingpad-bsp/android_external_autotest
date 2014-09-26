# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

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
    def __init__(self, image_comparer, stop_on_first_failure, threshold=0,
                 box=None):
        """
        @param image_comparer: object, image comparer to use.
        @param stop_on_first_failure: bool, true if the test should be stopped
                                      once a test image doesn't match its ref.
        @param threshold: int, a value which the pixel difference between test
                          image and golden image has to exceed before the
                          doublecheck comparer is used.
        @param box: int tuple, left, upper, right, lower pixel coordinates
                    defining a box region within which the comparison is made.

        """
        self.image_comparer = image_comparer
        self.stop_on_first_failure = stop_on_first_failure
        self.threshold = threshold
        self.box = box


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

        log_msgs = ["Threshold for diff pixel count = %d" % self.threshold]

        for g_image, t_image in zip(golden_image_paths, test_image_paths):

            with self.image_comparer:
                comp_res = self.image_comparer.compare(g_image,
                                                       t_image,
                                                       self.box)
                diff_pixels = comp_res.diff_pixel_count

            if diff_pixels > self.threshold:
                failure_count += 1

                log_msg = ("Image: %s. Pixel diff: %d." %
                           (os.path.basename(g_image), diff_pixels))

                logging.debug(log_msg)
                log_msgs.append(log_msg)

                if self.stop_on_first_failure:
                    raise error.TestError("%s. Bailing out." % log_msg)

        if failure_count > 0:
            cnt = len(golden_image_paths)
            # grab the parent link for comparison urls
            comparison_url = os.path.dirname(comp_res.comparison_url)

            report_mes = '''
            %d / %d test images were not golden
            Comparison url: %s
            %s
            ''' % (failure_count, cnt, comparison_url, '\t'.join(log_msgs))

            raise error.TestFail(report_mes)

        logging.debug("***All Good.***")