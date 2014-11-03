# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys


class ImageGenerator(object):
    """A class to generate the calibration images with different sizes.

    It generates the SVG images which are easy to be produced by changing its
    XML text content.

    """

    TEMPLATE_WIDTH = 1680
    TEMPLATE_HEIGHT = 1052
    TEMPLATE_FILENAME = 'template-%dx%d.svg' % (TEMPLATE_WIDTH, TEMPLATE_HEIGHT)

    # Note: change the coordinates if the image template changes.
    # Normalized coordinates of a maximum (i.e., white pixel) at (150, 15)
    MAX_X_NORM = 150.0 / TEMPLATE_WIDTH
    MAX_Y_NORM = 15.0 / TEMPLATE_HEIGHT
    # Normalized coordinates of a minimum (i.e., black pixel) at (80, 15)
    MIN_X_NORM = 80.0 / TEMPLATE_WIDTH
    MIN_Y_NORM = 15.0 / TEMPLATE_HEIGHT


    def __init__(self):
        """Construct an ImageGenerator.
        """
        module_dir = os.path.dirname(sys.modules[__name__].__file__)
        template_path = os.path.join(module_dir, 'calibration_images',
                                     self.TEMPLATE_FILENAME)
        self._image_template = open(template_path).read()


    def generate_image(self, width, height, filename):
        """Generate the image with the given width and height.

        @param width: The width of the image.
        @param height: The height of the image.
        @param filename: The filename to output.
        """
        with open(filename, 'w+') as f:
            logging.debug('Generate the image with size %dx%d to %s',
                          width, height, filename)
            f.write(self._image_template.format(
                    scale_width=float(width)/self.TEMPLATE_WIDTH,
                    scale_height=float(height)/self.TEMPLATE_HEIGHT))

    @staticmethod
    def get_extrema(image):
        """Returns a 2-tuple containing minimum and maximum values of the image.

        @param image: the calibration image projected by DUT.
        @return a tuple of (minimum, maximum)
        """
        w, h = image.size
        max_location = (int(ImageGenerator.MAX_X_NORM * w),
                        int(ImageGenerator.MAX_Y_NORM * h))
        min_location = (int(ImageGenerator.MIN_X_NORM * w),
                        int(ImageGenerator.MIN_Y_NORM * h))
        return (image.getpixel(min_location)[0],
                image.getpixel(max_location)[0])
