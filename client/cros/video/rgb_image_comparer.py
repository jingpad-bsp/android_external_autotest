# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from PIL import Image
from PIL import ImageChops

from autotest_lib.client.cros.video import method_logger


class RGBImageComparer(object):
    """
    Compares two RGB images using built-in python image library

    """

    def __enter__(self):
        return self


    @method_logger.log
    def compare(self, golden_img_path, test_img_path, box=None):
        """
        Compares a test image against a known golden image.

        Both images must be RGB images.

        @param golden_img_path: path, complete path to a golden image.
        @param test_img_path: path, complete path to a test image.
        @param box: int tuple, left, upper, right, lower pixel coordinates
                    defining a box region within which the comparison is made.

        @throws: ValueError if either image is not an RGB

        @return: int, number of pixels that are different.

        """
        golden_image = Image.open(golden_img_path)
        test_image = Image.open(test_img_path)

        if golden_image.mode != 'RGB' or test_image.mode != 'RGB':
            logging.debug("Golden image mode is %s", golden_image.mode)
            logging.debug("Test image mode is %s", test_image.mode)
            raise ValueError("Expected both images to be RGB. Bailing out.")

        if box is not None:
            golden_image = golden_image.crop(box)
            test_image = test_image.crop(box)

        diff_image = ImageChops.difference(golden_image, test_image)

        """
        If the two images are the same, the diff will be pure black. Diff image
        is also an RGB image whose histogram is a concatenated list of
        R histogram, G histogram and B histogram
        Full histogram will be a list with 256 * 3 = 768 elements
        h[0] contains all R pixels whose value is 0
        h[256] contains all G pixels whose value is 0
        h[512] contains all B pixels whose value is 0
        We must remove these values from the total count to find out the
        number of non black pixels in the diff image

        """

        hist = diff_image.histogram()

        logging.debug("Color counts")
        maxcolors = diff_image.size[0] * diff_image.size[1]
        logging.debug(diff_image.getcolors(maxcolors))

        differing_pixels = sum(hist) - hist[0] - hist[256] - hist[512]

        return differing_pixels


    def __exit__(self, exc_type, exc_val, exc_tb):
        pass