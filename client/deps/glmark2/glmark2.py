#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import os
from autotest_lib.client.bin import utils


PREFIX_DIR = '/usr/local/autotest/deps/glmark2'
version = 1


def setup(tarball, topdir):
    use_flags = os.environ.get('USE', '').split()
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    patches = ['0001-Fix-Clang-syntax-checking.patch']
    for patch in patches:
        utils.system('patch -p1 < ../%s' % patch)

    # USE-flag-specific behavior is specified here.
    if 'opengles' in use_flags:
        gl_target = '--enable-glesv2'
    else:
        gl_target = '--enable-gl'

    # glmark2 does not have any runtime option to specify its data dir, so we
    # have to set the prefix dir to where it's being run on target machine.
    # And we can only install glmark2 to inside the build sandbox (destdir), so
    # we have to do additional work to move the installed files to the correct
    # path and it will get installed on target machine correctly.
    utils.system('./waf configure %s --prefix=%s' % (gl_target, PREFIX_DIR))
    utils.system('./waf')
    utils.system('./waf install --destdir=%s' % topdir)
    utils.system('mv %s/* %s' % (topdir + PREFIX_DIR, topdir))
    utils.system('rm -rf %s/usr' % topdir)


# We got the source from
# https://launchpad.net/glmark2/trunk/2012.03/+download/glmark2-2012.03.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'glmark2-2012.03.tar.gz')
utils.update_version(pwd + '/src', True, version, setup, tarball, pwd)
