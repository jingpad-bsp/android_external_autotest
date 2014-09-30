# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser
import logging

from autotest_lib.client.cros.image_comparison import rgb_image_comparer
from autotest_lib.client.cros.image_comparison import upload_on_fail_comparer
from autotest_lib.client.cros.image_comparison import verifier
from autotest_lib.client.cros.image_comparison import bp_http_client
from autotest_lib.client.cros.image_comparison import bp_image_comparer
from autotest_lib.client.cros.video import method_logger


class ImageComparisonFactory(object):
    """
    Responsible for instantiating objects used in image comparison based tests.

    """


    def __init__(self, conf_filepath):
        """
        @param conf_filepath: path, full path to the conf file.

        """
        self.conf_filepath = conf_filepath
        self._load_configuration()


    def _load_configuration(self):
        """
        Loads values from configuration file.

        """

        parser = ConfigParser.SafeConfigParser()
        parser.read(self.conf_filepath)
        self.bp_base_projname = parser.get('biopic', 'project_name')
        self.bp_email = parser.get('biopic', 'contact_email')
        self.bp_wait_time = parser.getint('biopic',
                                          'wait_time_btwn_comparisons')
        self.bp_upload_retries = parser.getint('biopic', 'upload_retries')

        self.pixel_thres = parser.getint('rgb', 'rgb_pixel_threshold')

        self.pixel_count_thres = parser.getint('all', 'pixel_count_threshold')
        self.desired_comp_h = parser.getint('all', 'desired_comp_h')
        self.desired_comp_w = parser.getint('all', 'desired_comp_w')


    @method_logger.log
    def make_rgb_comparer(self):
        """
        @returns an RGBImageComparer object initialized with config. values.

        """
        return rgb_image_comparer.RGBImageComparer(self.pixel_thres)


    @method_logger.log
    def make_bp_comparer(self, project_name=None):
        """

        @param project_name: string, name of the project to use in bp.

        @returns a BpImageComparer object if it was successfully created, else
                 an RGBComparer object.

        """
        if not project_name:
            project_name = self.bp_base_projname
        return self._make_bp_comparer_helper(project_name)[0]


    @method_logger.log
    def make_upload_on_fail_comparer(self, project_name=None):
        """
        @param project_name: string, name of project to use in bp.

        @returns an UploadOnFailComparer object.

        """
        comparer, success = self._make_bp_comparer_helper(project_name)

        if success:
            # bp comparer was successfully made
            return upload_on_fail_comparer.UploadOnFailComparer(
                    self.make_rgb_comparer(),
                    comparer)

        # bp comparer was not made, we must have gotten rgb instead
        return comparer


    @method_logger.log
    def make_image_verifier(self, image_comparer, stop_on_first_failure=False):
        """
        @param image_comparer: any object that implements compare(). Currently,
                               it could BpImageComparer, RGBImageComparer or
                               UploadOnFailComparer.

        @param stop_on_first_failure: bool, True if we should stop the test when
                                      we encounter the first failed comparison.
                                      False if we should continue the test.
        @returns a Verifier object initialized with config. values.

        """
        if self.desired_comp_h == 0 or self.desired_comp_w == 0:
            box = None
        else:
            box = (0, 0, self.desired_comp_w, self.desired_comp_h)

        return verifier.Verifier(image_comparer,
                                 stop_on_first_failure,
                                 threshold=self.pixel_count_thres,
                                 box=box)


    def _make_bp_comparer_helper(self, project_name):
        """
        Internal helper method to make a BpImageComparer object.
        We use the try logic because sometime bp service is not availabe.In that
        case we should continue with the test and use a local comparer.

        @param project_name: string, name of project to use in bp.

        @returns a tuple containing (BpImageComparer object initialized with
                 config. values, True) if the initialization was successful.
                 Else (RGBImageComparer object, False).

        """
        success = False
        try:
            comparer = bp_image_comparer.BpImageComparer(project_name,
                                                         self.bp_email,
                                                         self.bp_wait_time,
                                                         self.bp_upload_retries)
            success = True
        except bp_http_client.BiopicClientError:
            logging.debug('**Could not make BpImageComparer. Defaulting to RGB')
            # we don't expect other kinds of exceptions to occur. If they do
            # we will know about it and decide what to do
            comparer = self.make_rgb_comparer()
        return comparer, success