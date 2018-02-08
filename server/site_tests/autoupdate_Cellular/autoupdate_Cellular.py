# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server.cros.update_engine import update_engine_test
from chromite.lib import retry_util


class autoupdate_Cellular(update_engine_test.UpdateEngineTest):
    """
    Tests auto updating over cellular.

    Usually with AU tests we use a lab devserver to hold the payload, and to be
    the omaha instance that DUTs ping. However, over cellular they will not be
    able to reach the devserver. So we will need to put the payload on a
    public google storage location. We will setup an omaha instance on the DUT
    (via autoupdate_CannedOmahaUpdate) that points to the payload on GStorage.

    """
    version = 1
    _UPDATE_ENGINE_LOG_FILE = '/var/log/update_engine.log'

    def cleanup(self):
        cmd = 'update_engine_client --update_over_cellular=no'
        retry_util.RetryException(error.AutoservRunError, 2, self._host.run,
                                  cmd)
        self._host.reboot()


    def _check_for_cellular_entries_in_update_log(self, update_engine_log):
        """
        Check update_engine.log for log entries about cellular.

        @param update_engine_log: The text of an update_engine.log file.

        """
        logging.info('Making sure we have cellular entries in update_engine '
                     'log.')
        line1 = "Allowing updates over cellular as permission preference is " \
                "set to true."
        line2 = "We are connected via cellular, Updates allowed: Yes"
        for line in [line1, line2]:
            ue = re.compile(line)
            if ue.search(update_engine_log) is None:
                raise error.TestFail('We did not find cellular string "%s" in '
                                     'the update_engine log. Please check the '
                                     'update_engine logs in the results '
                                     'directory.' % line)


    def run_once(self, host, job_repo_url=None, full_payload=True):
        self._host = host

        update_url = self.get_update_url_for_test(job_repo_url,
                                                  full_payload=full_payload,
                                                  cellular=True)
        logging.info('Update url: %s', update_url)

        # gs://chromeos-image-archive does not contain a handy .json file
        # with the payloads size and SHA256 info like we have for payloads in
        # gs://chromeos-releases. So in order to get this information we need
        # to use a devserver to stage the payloads and then call the fileinfo
        # API with the staged file URL. This will return the fields we need.
        payload = self._get_payload_url(full_payload=full_payload)
        staged_url = self._stage_payload_by_uri(payload)
        payload_info = self._get_staged_file_info(staged_url)

        cmd = 'update_engine_client --update_over_cellular=yes'
        retry_util.RetryException(error.AutoservRunError, 2, self._host.run,
                                  cmd)

        client_at = autotest.Autotest(self._host)
        client_at.run_test('autoupdate_CannedOmahaUpdate',
                           image_url=update_url,
                           image_size=payload_info['size'],
                           image_sha256=payload_info['sha256'],
                           use_cellular=True,
                           is_delta=not full_payload)

        client_at._check_client_test_result(self._host,
                                            'autoupdate_CannedOmahaUpdate')

        # Verify there are cellular entries in the update_engine log.
        update_engine_log = self._host.run('cat %s ' %
                                           self._UPDATE_ENGINE_LOG_FILE).stdout
        self._check_for_cellular_entries_in_update_log(update_engine_log)