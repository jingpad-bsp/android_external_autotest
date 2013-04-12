# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess

# Absolute path from INSIDE chroot.
DOWNLOAD_PATH = '/tmp/chromium-webdriver-parts'
WEBDRIVER = 'chromedriver'


def check_webdriver_binary():
    """Checks for presence of required webdriver binary.

    @returns a boolean, True if the binary is present.
    """
    webdriver_path = os.path.join(DOWNLOAD_PATH, WEBDRIVER)
    if not os.path.exists(webdriver_path):
        logging.error('Missing webdriver binary %r.', webdriver_path)
        return False
    logging.info('Located webdriver binary inside chroot.')
    return True


def download_chromium_prebuilt_binaries():
    """Ensure webdriver binary is downloaded and installed inside chroot.

    @returns a boolean, True iff webdriver binary is downloaded and installed.
    @raises IOError: if error fetching prebuilt binaries.
    """
    if check_webdriver_binary():
        return True

    # FIXME(tgao): this is a temporary hack until we completely and cleanly
    #              deprecates use of PyAuto across the board.
    fetch_prebuilt = os.path.join(os.path.dirname(__file__),
        '..', 'chaos_lib', 'fetch_prebuilt_pyauto.py')
    logging.info('Attempt to locate: %s', fetch_prebuilt)
    if not os.path.exists(fetch_prebuilt):
        raise IOError('Unable to locate: %s' % fetch_prebuilt)

    cmds = ['/usr/bin/python', fetch_prebuilt, '-d', DOWNLOAD_PATH, '-l']
    if subprocess.call(cmds, shell=False) != 0:
        raise IOError('fetch_prebuilt_pyauto.py threw an error, the download '
                      'was aborted. Please view stdout for more information.')
    logging.info('Successfully downloaded and installed prebuilt binaries to '
                 '%s (inside chroot).', DOWNLOAD_PATH)
    return True
