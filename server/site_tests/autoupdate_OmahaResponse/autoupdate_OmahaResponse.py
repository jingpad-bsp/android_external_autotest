# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.server import autotest
from autotest_lib.server.cros.update_engine import update_engine_test

class autoupdate_OmahaResponse(update_engine_test.UpdateEngineTest):
    """
    This server test is used just to get the URL of the payload to use. It
    will then call into a client side test to test different things in
    the omaha response (e.g switching between two urls, bad hash, bad SHA256).
    """
    version = 1

    def cleanup(self):
        self._host.reboot()
        super(autoupdate_OmahaResponse, self).cleanup()


    def run_once(self, host, job_repo_url=None, full_payload=True,
                 running_at_desk=False, switch_urls=False, bad_sha256=False,
                 bad_metadata_size=False, test_backoff=False, backoff=False):
        self._host = host
        self._job_repo_url = job_repo_url

        # Figure out the payload to use for the current build.
        payload = self._get_payload_url(full_payload=full_payload)
        image_url = self._stage_payload_by_uri(payload)
        file_info = self._get_staged_file_info(image_url)

        if running_at_desk:
            image_url = self._copy_payload_to_public_bucket(payload)
            logging.info('We are running from a workstation. Putting URL on a '
                         'public location: %s', image_url)

        if switch_urls:
            self._run_client_test_and_check_result('autoupdate_UrlSwitch',
                                                   image_url=image_url,
                                                   image_size=file_info['size'],
                                                   sha256=file_info['sha256'])

        if bad_sha256 or bad_metadata_size:
            sha = 'blahblah' if bad_sha256 else file_info['sha256']
            metadata = 123 if bad_metadata_size else None
            self._run_client_test_and_check_result('autoupdate_BadMetadata',
                                                   image_url=image_url,
                                                   image_size=file_info['size'],
                                                   sha256=sha,
                                                   metadata_size=metadata)

        if test_backoff:
            self._run_client_test_and_check_result('autoupdate_Backoff',
                                                   image_url=image_url,
                                                   image_size=file_info['size'],
                                                   sha256=file_info['sha256'],
                                                   backoff=backoff)
