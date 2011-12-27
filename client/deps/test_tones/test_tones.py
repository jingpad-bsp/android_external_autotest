#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(fftw_tarball, topdir):
    srcdir = os.path.join(topdir, 'src')

    # Setup fftw
    fftwdir = os.path.join(topdir, 'fftw')
    utils.extract_tarball_to_dir(fftw_tarball, fftwdir)
    os.chdir(fftwdir)
    utils.configure('--prefix=%s' % srcdir) #topdir)
    utils.make()
    utils.system('make install')
    os.chdir(topdir)

    os.chdir(srcdir)
    utils.make()
    os.chdir(topdir)

pwd = os.getcwd()
fftw_tarball = os.path.join(pwd, 'fftw-3.3.tar.gz')
utils.update_version(pwd+'/src', True, version, setup, fftw_tarball, pwd)
