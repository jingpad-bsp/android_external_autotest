#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'nsanders@chromium.org (Nick Sanders)'

import common, os, re
from autotest_lib.client.bin import utils

version = 1

def target_is_x86():
  result = utils.system_output('${CC} -dumpmachine', retain_output=True,
                               ignore_status=True)
  x86_pattern = re.compile(r"^i.86.*")
  return x86_pattern.match(result)


def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    # 'Add' arm support.
    os.chdir(srcdir)
    utils.system('patch -p0 < ../iotools.arm.patch')
    # TODO(fes): Remove this if there is a better way to detect that we are
    # in a hardened build (or if this later properly picks up the
    # -nopie flag from portage)
    if os.path.exists('/etc/hardened') and target_is_x86():
        utils.system('patch -p0 < ../iotools.nopie.patch')

    utils.system('CROSS_COMPILE=${CTARGET_default}- make')
    utils.system('cp iotools %s' % topdir)
    os.chdir(topdir)


# The source is grabbed from
# http://iotools.googlecode.com/files/iotools-1.2.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'iotools-1.2.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
