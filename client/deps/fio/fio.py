#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, os, shutil
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system('patch -p1 < ../Makefile.patch')
    utils.system('patch -p0 < ../crc32c-intel.patch')
    utils.system('patch -p1 < ../arm.patch')

    #TODO: Fix this in the makefile.
    autodir = os.environ['AUTODIR']
    ldflags = '-L' + autodir + '/deps/libaio/lib'
    cflags = '-I' + autodir + '/deps/libaio/include'
    var_ldflags = 'LDFLAGS="' + ldflags + '"'
    var_cflags  = 'CFLAGS="' + cflags + '"'
    utils.make(make='%s %s make' % (var_ldflags, var_cflags))


# src from http://brick.kernel.dk/snaps/
pwd = os.getcwd()
tarball = os.path.join(pwd, 'fio-1.50.2.tar.bz2')
utils.update_version(pwd + '/src', True, version, setup, tarball, pwd)
