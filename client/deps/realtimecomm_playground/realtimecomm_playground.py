#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, os
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'GTalkPlayground.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
