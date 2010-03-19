# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class graphics_GLAPICheck(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make all')


    def __check_extensions(self, info, ext_entries):
        info_split = info.split()
        for extension in ext_entries:
            match = extension in info_split
            if not match:
                logging.info("MISSING: %s" % extension)
                return False
        return True


    def __check_gl_extensions_1x(self, info):
        extensions = [
            'GL_ARB_vertex_buffer_object',
            'GL_ARB_shader_objects',
            'GL_ARB_texture_non_power_of_two',
            'GL_ARB_point_sprite',
            'GL_EXT_framebuffer_object',
            'GLX_EXT_texture_from_pixmap'
        ]
        return self.__check_extensions(info, extensions)


    def __check_gl_extensions_2x(self, info):
        extensions = [
            'GL_EXT_framebuffer_object',
            'GLX_EXT_texture_from_pixmap'
        ]
        return self.__check_extensions(info, extensions)


    def __check_gles_extensions(self, info):
        extensions = [
            'EGL_KHR_image_pixmap',
            'GL_OES_EGL_image',
            'GL_OES_texture_npot'
        ]
        return self.__check_extensions(info, extensions)


    def __check_gl(self, result):
        version_pattern = re.compile(r"GL_VERSION = ([0-9]+).([0-9]+).+")
        version = version_pattern.findall(result)
        if len(version) == 1:
            version_major = int(version[0][0])
            version_minor = int(version[0][1])
            logging.info("GL_VERSION = %d.%d" %
                         (version_major, version_minor))
            if version_major == 1:
                if version_minor < 4:
                    return False
                return self.__check_gl_extensions_1x(result)
            elif version_major >= 2:
                return self.__check_gl_extensions_2x(result)
            else:
                return False
        # No GL version info found.
        return False


    def __check_gles(self, result):
        version_pattern = re.compile(
            r"GLES_VERSION = OpenGL ES.* ([0-9]+).([0-9]+)")
        version = version_pattern.findall(result)
        if len(version) == 1:
            # GLES version has to be 2.0 or above.
            version_major = int(version[0][0])
            version_minor = int(version[0][1])
            logging.info("GLES_VERSION = %d.%d" %
                         (version_major, version_minor))
            if version_major < 2:
                return False;
            # EGL version has to be 1.3 or above.
            version_pattern = re.compile(
                r"EGL_VERSION = ([0-9]+).([0-9]+)")
            version = version_pattern.findall(result)
            if len(version) == 1:
                version_major = int(version[0][0])
                version_minor = int(version[0][1])
                logging.info("EGL_VERSION = %d.%d" %
                             (version_major, version_minor))
                if version_major >= 1 and version_minor >= 3:
                    return self.__check_gles_extensions(result)
                else:
                    return False
            # No EGL version info found.
            return False
        # No GLES version info found.
        return False


    def __check_x_extensions(self, result):
        extensions = [
            'DAMAGE',
            'Composite'
        ]
        return self.__check_extensions(result, extensions)


    def __run_x_cmd(self, cmd):
        cmd = "DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority " + cmd
        result = utils.system_output(cmd, retain_output=True,
                                     ignore_status=True)
        return result


    def run_once(self):
        test_done = False

        # Run graphics_GLAPICheck first.  If failed, run gles_APICheck next.
        cmd = os.path.join(self.bindir, 'graphics_GLAPICheck')
        result = self.__run_x_cmd(cmd)
        error_pattern = re.compile(r"ERROR: \[(.+)\]")
        errors = error_pattern.findall(result)
        run_through_pattern = re.compile(r"SUCCEED: run to the end")
        run_through = run_through_pattern.findall(result)
        if len(errors) == 0 and len(run_through) > 0:
            check_result = self.__check_gl(result)
            if check_result == False:
                raise error.TestFail('GL API insufficient')
            test_done = True;

        if not test_done:
            cmd = (os.path.join(self.bindir, 'gles_APICheck') +
                   ' libGLESv2.so libEGL.so')
            # TODO(zmo@): smarter mechanism with GLES & EGL library names.
            result = self.__run_x_cmd(cmd)
            error_pattern = re.compile(r"ERROR: \[(.+)\]")
            errors = error_pattern.findall(result)
            run_through_pattern = re.compile(r"SUCCEED: run to the end")
            run_through = run_through_pattern.findall(result)
            if len(errors) == 0 and len(run_through) > 0:
                check_result = self.__check_gles(result)
                if check_result == False:
                    raise error.TestFail('GLES API insufficient')
                test_done = True;

        if not test_done:
            raise error.TestFail('No sufficient GL/GLES API detected')

        # Check X11 extensions.
        check_result = self.__check_x_extensions(result)
        if check_result == False:
            raise error.TestFail('X extensions insufficient')
