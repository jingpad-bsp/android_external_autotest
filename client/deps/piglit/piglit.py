#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil
from autotest_lib.client.bin import test, utils

# changing this version number will force a delete of piglit/ and remake
version = 2

# TODO(ihf) piglit only builds on x86, Tegra2 only supports GLES
def setup(topdir):
    sysroot = os.environ.get("SYSROOT", "")
    logging.debug('INFO: piglit sysroot = %s' % sysroot)
    tarball = 'piglit.tar.gz'
    srcdir = os.path.join(topdir, 'src')
    tarball_path = os.path.join(srcdir, tarball)
    dst_path = os.path.join(topdir, 'piglit')
    # in-source build, clean/overwrite destination
    shutil.rmtree(dst_path, ignore_errors=True)
    if re.search('x86', sysroot.lower()):
        utils.extract_tarball_to_dir(tarball_path, dst_path)
        # patch in files now
        utils.system('patch -p0 < ' +
                     os.path.join(srcdir, 'CMakeLists_GLES.patch'))
        shutil.copyfile(os.path.join(srcdir, 'cros-driver.tests'),
                        os.path.join(dst_path, 'tests/cros-driver.tests'))
        os.chdir(dst_path)
        # we have to tell cmake where to find glut
        cmd = 'cmake  -DCMAKE_FIND_ROOT_PATH=' + sysroot
        cmd = cmd + ' -DGLUT_INCLUDE_DIR=' + sysroot + '/usr/include'
        cmd = cmd + ' -DGLUT_glut_LIBRARY=' + sysroot + '/usr/lib/libglut.so'
        utils.run(cmd)
        utils.make('-j %d' % utils.count_cpus())
        # strip symbols from all binaries to save space
        # TODO(ihf): strip everything once issue 14447 is resolved
        # except for fbo-dept-sample-compare
        utils.run("find bin/ -type f \! -name 'fbo-depth-sample-compare' "
                  " -exec strip {} \;")
        os.chdir(topdir)
    else:
        logging.warning('WARNING: Skip piglit build. OpenGL/x86 boards only')
        dst_path = os.path.join(topdir, 'piglit')
        # still create an empty directory
        if not os.path.exists(dst_path):
            os.makedirs(dst_path)

pwd = os.getcwd()
# delete piglit directory when new version is set
utils.update_version(pwd+'/piglit', False, version, setup, pwd)
