#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, os, shutil
from autotest_lib.client.bin import utils

version = 1

def setup(topdir):
    my_srcdir = os.path.join(topdir, 'src.orig')
    srcdir = os.path.join(topdir, 'src')
    shutil.move(my_srcdir, srcdir)
    os.chdir(srcdir)
    utils.system('make')
    os.chdir(topdir)

pwd = os.getcwd()
utils.update_version(pwd + '/src', False, version, setup, pwd)
