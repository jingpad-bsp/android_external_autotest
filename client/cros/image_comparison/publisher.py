# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import shutil

class ImageDiffPublisher(object):
    """
    Class that takes care of creating the HTML file output when a pdiff
    comparison fails. It moves each of the three images to a folder in the
    results directory. It then writes a html file that references these images.

    """

    VIEWER_FILES = '/usr/local/autotest/cros/image_comparison/diffviewer/*'

    def __init__(self, results_folder):
        """
        @param results_folder: path, where to publish to
        """
        self.results_folder = results_folder

    def publish(self, golden_image_path, test_image_path, diff_image_path,
                tags):
        """
        Move three images and viewer files to the results folder.
        Write tags to HTML file.

        @param golden_image_path: path, complete path to a golden image.
        @param test_image_path: path, complete path to a test image.
        @param diff_image_path: path, complete path to a diff image.
        @param tags: list, run information.
        """

        try:
            # Copy the html, css and js needed for the viewer to resultsdir
            for diff_viewer_file in glob.glob(self.VIEWER_FILES):
                shutil.copy(diff_viewer_file, self.results_folder)

            output_folder = self.results_folder
            shutil.move(golden_image_path, os.path.join(output_folder,
                                                        'golden.png'))
            shutil.move(test_image_path, os.path.join(output_folder,
                                                      'test.png'))
            shutil.move(diff_image_path, os.path.join(output_folder,
                                                      'diff.png'))
        except shutil.Error as error:
            logging.debug('Failed to copy all images and viewer files to '
                          'results directory.')
            logging.debug(error)
            raise

        self._write_tags_to_html(output_folder, tags)

    def _write_tags_to_html(self, output_folder, tags,
                            html_filename='index.html'):
        """
        Writes tags to the HTML file
        """
        html_file_fullpath = os.path.join(output_folder,
                                          html_filename)

        with open(html_file_fullpath, 'r+') as f:
            html = f.read()
            formatted_html = html.format(*tags)
            f.seek(0)
            f.write(formatted_html)
