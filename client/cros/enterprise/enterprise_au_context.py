# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.update_engine import nano_omaha_devserver
from autotest_lib.client.cros.update_engine import update_engine_util

_MIN_BUILD = '0.0.0'
_MAX_BUILD = '999999.0.0'

class NanoOmahaEnterpriseAUContext(object):
    """
    Contains methods required for Enterprise AU tests using Nano Omaha.

    """

    def __init__(self, image_url, image_size, sha256, to_build=_MAX_BUILD,
                 from_build=_MIN_BUILD, is_rollback=False, is_critical=False):
        """
        Start a Nano Omaha instance and intialize variables.

        @param image_url: Url of update image.
        @param image_size: Size of the update.
        @param sha256: Sha256 hash of the update.
        @param to_build: String of the build number Nano Omaha should serve.
        @param from_build: String of the build number this device should say
                           it is on by setting lsb_release.
        @param is_rollback: whether the build should serve with the rollback
                            flag.
        @param is_critical: whether the build should serve marked as critical.

        """
        self._omaha = nano_omaha_devserver.NanoOmahaDevserver()
        self._omaha.set_image_params(image_url, image_size, sha256,
                                     build=to_build, is_rollback=is_rollback)
        self._omaha.start()

        self._au_util = update_engine_util.UpdateEngineUtil()

        update_url = self._omaha.get_update_url()
        self._au_util._create_custom_lsb_release(from_build, update_url)


    def update_and_poll_for_update_start(self):
        """
        Check for an update and wait until it starts.

        @raises: error.TestFail when update does not start after timeout.

        """
        self._au_util._check_for_update(port=self._omaha.get_port())

        def update_started():
            """Polling function: True or False if update has started."""
            status = self._au_util._get_update_engine_status()
            logging.info('Status: %s', status)
            return (status[self._au_util._CURRENT_OP]
                    == self._au_util._UPDATE_ENGINE_DOWNLOADING)

        utils.poll_for_condition(
                update_started,
                exception=error.TestFail('Update did not start!'))


    def get_update_requests(self):
        """
        Get the contents of all the update requests from the most recent log.

        @returns: a sequential list of <request> xml blocks or None if none.

        """
        return self._au_util._get_update_requests()


    def get_time_of_last_update_request(self):
        """
        Get the time of the last update request from most recent logfile.

        @returns: seconds since epoch of when last update request happened
                  (second accuracy), or None if no such timestamp exists.

        """
        return self._au_util._get_time_of_last_update_request()
