# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

DOWNLOAD_PATH = '/tmp/chromium-webdriver-parts'

def check_for_chromium_prebuilt_binaries():
    chromium_parts = ['chrome', 'chromedriver', 'pyautolib.py', '_pyautolib.so']
    for part in chromium_parts:
        chromium_part = os.path.join(DOWNLOAD_PATH, part)
        if not os.path.exists(chromium_part):
            return False
    return True

def download_chromium_prebuilt_binaries():
    if check_for_chromium_prebuilt_binaries():
        return False
    fetch_prebuilt = os.path.join(os.path.dirname(__file__),
        '..', '..', 'deps', 'chrome_test', 'test_src', 'chrome', 'test',
        'pyautolib', 'fetch_prebuilt_pyauto.py')
    if not os.path.exists(fetch_prebuilt):
        raise IOError('Unable to locate pyauto components.  Is the chromium '
                      'code synced and available?  Checking : %s'
                      % fetch_prebuilt)
    subprocess.call(['/usr/bin/python', fetch_prebuilt, '-d', DOWNLOAD_PATH,
                     '-l'], shell=False)
    return True
