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
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    patches = ['0001-Fix-Clang-syntax-checking.patch']
    for patch in patches:
        utils.system('patch -p1 < ../%s' % patch)

    gl_option = '--enable-gl'
    if 'GRAPHICS_BACKEND' in os.environ:
        graphics_backend = os.environ.get('GRAPHICS_BACKEND')
        if graphics_backend == 'OPENGLES':
            gl_option = '--enable-glesv2'

    # glmark2 does not have any runtime option to specify its data dir, so we
    # have to set the prefix dir to where it's being run on target machine.
    # And we can only install glmark2 to inside the build sandbox (destdir), so
    # we have to do additional work to move the installed files to the correct
    # path and it will get installed on target machine correctly.
    utils.system('./waf configure %s --prefix=%s' % (gl_option, PREFIX_DIR))
    utils.system('./waf')
    utils.system('./waf install --destdir=%s' % topdir)
    utils.system('mv %s/* %s' % (topdir + PREFIX_DIR, topdir))
    utils.system('rm -rf %s/usr' % topdir)


# We got the source from
# https://launchpad.net/glmark2/trunk/2012.03/+download/glmark2-2012.03.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'glmark2-2012.03.tar.gz')
utils.update_version(pwd + '/src', True, version, setup, tarball, pwd)
