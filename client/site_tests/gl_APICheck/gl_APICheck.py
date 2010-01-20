# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class gl_APICheck(test.test):
    version = 1

    def setup(self):
        os.chdir(self.bindir)
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
        # OpenGL.
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
        # OpenGL ES.
        version_pattern = re.compile(
            r"GLES_VERSION = ([0-9]+).([0-9]+)")
        version = version_pattern.findall(result)
        if len(version) == 1:
            version_major = int(version[0][0])
            version_minor = int(version[0][1])
            logging.info("GLES_VERSION = %d.%d" %
                         (version_major, version_minor))
            if version_major >= 1 and version_minor >= 3:
                return self.__check_gles_extensions(result)
            else:
                return False
        # No version info found.
        return False

    def __check_x_extensions(self, result):
        extensions = [
            'DAMAGE',
            'Composite'
        ]
        return self.__check_extensions(result, extensions)

    def run_once(self):
        # Run gl_APICheck first.  If failed, run gles_APICheck next.
        cmd = os.path.join(self.bindir, 'gl_APICheck')
        result = utils.system_output(cmd, retain_output = True)
        error_pattern = re.compile(r"ERROR: \[(.+)\]")
        errors = error_pattern.findall(result)
        if len(errors) > 0:
            cmd = os.path.join(self.bindir, 'gles_APICheck')
            result = utils.system_output(cmd, retain_output = True)
            error_pattern = re.compile(r"ERROR: \[(.+)\]")
            errors = error_pattern.findall(result)
            if len(errors) > 0:
                raise error.TestFail("can't perform gl API check");
        
        # Check GL/GLES version/extensions check.
        check_result = self.__check_gl(result)
        if check_result == False:
            raise error.TestFail('GL version/extensions insufficient')

        # Check X11 extensions.
        check_result = self.__check_x_extensions(result)
        if check_result == False:
            raise error.TestFail('X extensions insufficient')
