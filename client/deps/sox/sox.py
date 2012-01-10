#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system('patch < ../configure_no_gsm.patch')
    utils.configure('--disable-gomp --without-sndfile --without-magic' +
            ' --prefix=%s' % topdir)
    utils.make()
    utils.system('make install')
    os.chdir(topdir)


# The source is grabbed from
# http://sourceforge.net/projects/sox/files/sox/sox-14.3.2.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'sox-14.3.2.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
