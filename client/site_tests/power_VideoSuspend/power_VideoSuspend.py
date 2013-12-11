# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, sys_power

def download(url):
    """
    Download a file to the local download directory.

    Returns the URL to the downloaded file.
    """
    logging.info('downloading %s', url)
    path = utils.unmap_url('', url, '/home/chronos/user/Downloads/')
    if not os.path.isfile(path):
        raise error.TestError('downloaded file missing: %s' % path)
    return 'file://' + path


class power_VideoSuspend(cros_ui_test.UITest):
    """Suspend the system with a video playing."""

    def run_once(self, video_urls=None):
        if video_urls is None:
            raise error.TestError('no videos to play')

	# We need access to the Internet to download the video files,
	# temporarily stop the local fake DNS and authentication server.
	self.stop_authserver()
        local_video_urls = [download(url) for url in video_urls]
	self.start_authserver()

        for url in local_video_urls:
            self.suspend_with_video(url)

    def suspend_with_video(self, url):
        logging.info('playing %s', url)
        self.pyauto.NavigateToURL(url)

        # Wait for video to start playing.
        # TODO(spang): Make this sane. crosbug.com/37452
        time.sleep(5)

        sys_power.kernel_suspend(10)
        # TODO(spang): Check video is still playing. crosbug.com/37452

        logging.info('done %s', url)
