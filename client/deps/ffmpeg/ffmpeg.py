#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, os, shutil
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

version = 1

def setup(topdir):
    test_binary = 'ffmpeg_tests'
    sysroot = os.environ['SYSROOT']
    origin = os.path.join(sysroot,
        'usr/local/autotest/client/deps/chrome_test/test_src',
        test_binary)
    if not os.path.exists(origin):
        raise error.TestError('Could not find file %s' % origin)
    shutil.copy(origin, topdir)

pwd = os.getcwd()
utils.update_version(pwd, True, version, setup, pwd)
