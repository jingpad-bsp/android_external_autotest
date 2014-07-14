# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.cros.video import bp_http_client, method_logger


class BpImageComparer(object):
    """
    Encapsulates the BioPic image comparison strategy.

    """


    @method_logger.log
    def __init__(self, project_name, contact_email, wait_time_btwn_comparisons,
                 retries):
        """
        Initializes the underlying bp client.

        @param project_name: string, name of test run project to view results.
        @param contact_email: string, email to receive test results on failure.
        @param wait_time_btwn_comparisons: int, time in seconds to wait between
                                           two consecutive pair of calls to
                                           upload reference and test images.
                                           If we upload without a break, biopic
                                           server could get overwhelmed and
                                           throw an exception.
        @param retries: int, number of times to retry upload before giving up.

        """
        self.bp_client = bp_http_client.BiopicClient(project_name)
        self.test_run = self.bp_client.CreateTestRun(contact_email)
        self.wait_time_btwn_comparisons = wait_time_btwn_comparisons
        self.retries = retries


    def __enter__(self):
        """
         Enables BpImageComparer to be used with the 'with' construct.

         Using this class with the 'with' construct guarantees EndTestRun will
         be called.

         @returns this current object.

        """
        return self


    def _upload_image_with_retry(self, bp_upload_function, image_path, retries):
        """
        Uploads a golden image or run image to biopic, retries on upload fail.

        @param bp_upload_function: Function to call to upload either the golden
                                   or test image.
        @param image_path: path, complete path to the image.
        @param retries: number of times to retry uploading before giving up.
                        NOTE: if retries = 1 that means we will upload the first
                        time if that fails we will retry once bringing the total
                        number of upload tries to TWO (2)..
        @throws: Whatever exception biopic threw if no more retries are left.
        """

        while True:

            try:
                res = bp_upload_function(self.id, image_path)
                return res  # Great Success!!

            except bp_http_client.BiopicClientError as e:
                e.msg = """ BiopicClientError thrown while uploading image %s.
                Original message: %s""" % image_path, e.msg

                logging.debug(e)
                logging.debug("RETRY LEFT : %d", retries)

                if retries == 0:
                    raise

                retries -= 1

    @property
    def id(self):
        """
        Returns the id of the testrun.

        """
        return self.test_run['testrun_id']


    @method_logger.log
    def compare(self, golden_image_paths, test_run_image_paths, retries=None):
        """
        Compares a test image with a known reference image.

        Uses http_client interface to communicate with biopic service.

        @param golden_image_paths: path, complete path to golden image.
        @param test_run_image_paths: path, complete path to test image.
        @param retries: int, number of times to retry before giving up.
                        This is configured at object creation but test can
                        override the configured value at method call.

        @raises whatever biopic http interface raises.

        @returns a list of dictionaries containing test results.

        """

        if retries is None:
            retries = self.retries

        if type(golden_image_paths) is not list:
            golden_image_paths = [golden_image_paths]

        if type(test_run_image_paths) is not list:
            test_run_image_paths = [test_run_image_paths]

        upload_results = []

        logging.debug("*** Beginning Biopic Upload ... **** \n")

        for gimage, timage in zip(golden_image_paths, test_run_image_paths):

            rs = self._upload_image_with_retry(self.bp_client.UploadGoldenImage,
                                               gimage,
                                               retries)

            logging.debug(rs)
            upload_results.append(rs)

            rs = self._upload_image_with_retry(self.bp_client.UploadRunImage,
                                                timage,
                                                retries)

            logging.debug(rs)
            upload_results.append(rs)

            time.sleep(self.wait_time_btwn_comparisons)

        logging.debug("*** Biopic Upload COMPLETED. **** \n")

        return upload_results


    def complete(self):
        """
        Completes the test run.

        Biopic service requires its users to end the test run when finished.

        """
        self.bp_client.EndTestRun(self.id)


    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ends the test run. Meant to be used with the 'with' construct.

        """
        self.complete()
