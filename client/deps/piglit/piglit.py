#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, logging, os, re, shutil
from autotest_lib.client.bin import test, utils

# changing this version number will force a delete of piglit/ and remake
version = 2

# TODO(ihf) piglit only builds on x86, Tegra2 only supports GLES
def setup(topdir):
    sysroot = os.environ.get("SYSROOT", "")
    # This gets the proper lib directory of "lib" or "lib64" from an
    # environment variable defined by the ebuild
    glut_libdir = os.environ.get("GLUT_LIBDIR", "")  + '/'
    if glut_libdir == "/":
        glut_libdir = '/usr/lib/'
    glut_libpath = sysroot + glut_libdir + 'libglut.so'
    logging.debug('INFO: piglit sysroot = %s' % sysroot)
    logging.debug('INFO: glut_libpath = %s' % glut_libpath)
    tarball = 'piglit.tar.gz'
    srcdir = os.path.join(topdir, 'src')
    tarball_path = os.path.join(srcdir, tarball)
    dst_path = os.path.join(topdir, 'piglit')
    # in-source build, clean/overwrite destination
    shutil.rmtree(dst_path, ignore_errors=True)
    if utils.target_is_x86():
        utils.extract_tarball_to_dir(tarball_path, dst_path)
        # patch in files now
        utils.system('patch -p0 < ' +
                     os.path.join(srcdir, 'CMakeLists_GLES_Release.patch'))
        utils.system('patch -p0 < ' +
                     os.path.join(srcdir,
                     'monitor_tests_for_GPU_hang_and_SW_rasterization.patch'))
        shutil.copyfile(os.path.join(srcdir, 'cros-driver.tests'),
                        os.path.join(dst_path, 'tests/cros-driver.tests'))
        os.chdir(dst_path)
        # we have to tell cmake where to find glut
        cmd = 'cmake  -DCMAKE_FIND_ROOT_PATH=' + sysroot
        cmd = cmd + ' -DGLUT_INCLUDE_DIR=' + sysroot + '/usr/include'
        cmd = cmd + ' -DGLUT_glut_LIBRARY=' + glut_libpath
        utils.run(cmd)
        utils.make('-j %d' % utils.count_cpus())
        # strip symbols from all binaries to save space
        # TODO(ihf): strip everything once issue 30287 is resolved
        #utils.run("find bin/ -type f \! -name 'fbo-depth-sample-compare' "
        #          " -exec strip {} \;")
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
