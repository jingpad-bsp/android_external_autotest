# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
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

    JS = """
      $(document).ready(function() {
          $("#fullsizeimage").attr("src", $("#golden").attr("src"));
          $(".thumb").click(function() {
              $("#fullsizeimage").attr("src", $(this).attr("src"));
          });
      });
    """

    CSS = """
     #testrundetails {
          height: 200px;
        }

        #thumbnails {
          top: 250px;
          left: 10px;
          width: 260px;
          margin: 0px;
          padding: 0px;
          position: absolute;
        }

        .thumb {
          width: 200px;
          height: auto;
          cursor: pointer;
          border: 3px solid black;
        }

        .thumb:hover {
          border: 3px solid blue;
        }

        #content {
          margin-left: 260px;
        }

        .tagname {
           font-weight: bold;
        }
    """

    def __init__(self, results_folder):
        """
        @param results_folder: path, where to publish to
        """
        self.results_folder = results_folder

    def publish(self, golden_image_path, test_image_path, diff_image_path,
                tags):
        """
        Move viewer files to the results folder and base64 encode the images.
        Write tags to HTML file.

        @param golden_image_path: path, complete path to a golden image.
        @param test_image_path: path, complete path to a test image.
        @param diff_image_path: path, complete path to a diff image.
        @param tags: list, run information.
        """

        try:
            # Copy the files needed for the viewer to resultsdir
            for diff_viewer_file in glob.glob(self.VIEWER_FILES):
                shutil.copy(diff_viewer_file, self.results_folder)

        except shutil.Error as error:
            logging.debug('Failed to copy files to results directory')
            logging.debug(error)
            raise

        # Encode the images to base64
        base64_images = []
        with open(golden_image_path, "rb") as image_file:
            base64_images.append(base64.b64encode(image_file.read()))
        with open(test_image_path, "rb") as image_file:
            base64_images.append(base64.b64encode(image_file.read()))
        with open(diff_image_path, "rb") as image_file:
            base64_images.append(base64.b64encode(image_file.read()))

        # Append all of the things we push to the html template
        tags = [self.CSS, self.JS] + tags + base64_images

        html_file_fullpath = os.path.join(self.results_folder, 'index.html')
        self._write_tags_to_html(tags, html_file_fullpath)

    def _write_tags_to_html(self, tags, html_filename):
        """
        Writes tags to the HTML file

        @param tags the tags to write into the html template
        @param html_filename the full path to the html template
        """

        with open(html_filename, 'r+') as f:
            html = f.read()
            formatted_html = html.format(*tags)
            f.seek(0)
            f.write(formatted_html)
