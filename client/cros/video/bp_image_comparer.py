# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros.video import bp_http_client, method_logger


class BpImageComparer(object):
    """
    Encapsulates the BioPic image comparison strategy.

    """


    @method_logger.log
    def __init__(self, project_name, contact_email):
        """
        Initializes the underlying bp client.

        @param project_name: string, name of test run project to view results.
        @param contact_email: string, email to receive test results on failure.

        """
        self.bp_client = bp_http_client.BiopicClient(project_name)
        self.test_run = self.bp_client.CreateTestRun(contact_email)


    def __enter__(self):
        """
         Enables BpImageComparer to be used with the 'with' construct.

         Using this class with the 'with' construct guarantees EndTestRun will
         be called.

         @returns this current object.

        """
        return self


    @property
    def id(self):
        """
        Returns the id of the testrun.

        """
        return self.test_run['testrun_id']


    @method_logger.log
    def compare(self, golden_image_path, test_run_image_path):
        """
        Compares a test image with a known reference image.

        Uses http_client interface to communicate with biopic service.

        @param golden_image_path: path, complete path to golden image.
        @param test_run_image_path: path, complete path to test image.

        @raises whatever biopic http interface raises.

        @returns a dictionary with various test results including urls.


        """
        self.bp_client.UploadGoldenImage(self.id, golden_image_path)
        return self.bp_client.UploadRunImage(self.id, test_run_image_path)


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
