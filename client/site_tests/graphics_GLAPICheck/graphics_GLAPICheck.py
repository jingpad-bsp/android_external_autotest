# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import site_login, site_ui_test
from autotest_lib.client.common_lib import error, site_ui, utils

class graphics_GLAPICheck(site_ui_test.UITest):
    version = 1
    preserve_srcdir = True
    error_message = ""


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make all')


    def __check_extensions(self, info, ext_entries):
        info_split = info.split()
        comply = True
        for extension in ext_entries:
            match = extension in info_split
            if not match:
                self.error_message += " " + extension
                comply = False
        return comply


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
        version = re.findall(r"GL_VERSION = ([0-9]+).([0-9]+).+", result)
        if version:
            version_major = int(version[0][0])
            version_minor = int(version[0][1])
            version_info = (" GL_VERSION = %d.%d" %
                            (version_major, version_minor))
            if version_major == 1:
                if version_minor < 4:
                    self.error_message = version_info
                    return False
                return self.__check_gl_extensions_1x(result)
            elif version_major >= 2:
                return self.__check_gl_extensions_2x(result)
            else:
                self.error_message = version_info
                return False
        # No GL version info found.
        self.error_message = " missing GL version info"
        return False


    def __check_gles(self, result):
        version = re.findall(r"GLES_VERSION = OpenGL ES.* ([0-9]+).([0-9]+)",
                             result)
        if version:
            # GLES version has to be 2.0 or above.
            version_major = int(version[0][0])
            version_minor = int(version[0][1])
            version_info = (" GLES_VERSION = %d.%d" %
                            (version_major, version_minor))
            if version_major < 2:
                self.error_message = version_info
                return False;
            # EGL version has to be 1.3 or above.
            version = re.findall(r"EGL_VERSION = ([0-9]+).([0-9]+)", result)
            if version:
                version_major = int(version[0][0])
                version_minor = int(version[0][1])
                version_info = ("EGL_VERSION = %d.%d" %
                                (version_major, version_minor))
                if (version_major == 1 and version_minor >= 3 or
                    version_major > 1):
                    return self.__check_gles_extensions(result)
                else:
                    self.error_message = version_info
                    return False
            # No EGL version info found.
            self.error_message = " missing EGL version info"
            return False
        # No GLES version info found.
        self.error_message = " missing GLES version info"
        return False


    def __check_x_extensions(self, result):
        extensions = [
            'DAMAGE',
            'Composite'
        ]
        return self.__check_extensions(result, extensions)


    def __run_x_cmd(self, cmd):
        cmd = site_ui.xcommand(cmd)
        result = utils.system_output(cmd, retain_output=True,
                                     ignore_status=True)
        return result


    def run_once(self):
        test_done = False
        cmd_gl = os.path.join(self.bindir, 'gl_APICheck')
        cmd_gles = os.path.join(self.bindir, 'gles_APICheck')
        exist_gl = os.path.isfile(cmd_gl)
        exist_gles = os.path.isfile(cmd_gles)
        if not exist_gl and not exist_gles:
            raise error.TestFail('Found neither gl_APICheck nor gles_APICheck. '
                                 'Test setup error.')

        # Run gl_APICheck first.  If failed, run gles_APICheck next.
        if exist_gl:
            self.error_message = ""
            result = self.__run_x_cmd(cmd_gl)
            errors = re.findall(r"ERROR: ", result)
            run_through = re.findall(r"SUCCEED: run to the end", result)
            if not errors and run_through:
                check_result = self.__check_gl(result)
                if not check_result:
                    raise error.TestFail('GL API insufficient:' +
                                         self.error_message)
                test_done = True;

        if not test_done and exist_gles:
            self.error_message = ""
            # TODO(zmo@): smarter mechanism with GLES & EGL library names.
            result = self.__run_x_cmd(cmd_gles + ' libGLESv2.so libEGL.so')
            errors = re.findall(r"ERROR: ", result)
            run_through = re.findall(r"SUCCEED: run to the end", result)
            if not errors and run_through:
                check_result = self.__check_gles(result)
                if not check_result:
                    raise error.TestFail('GLES API insufficient:' +
                                         self.error_message)
                test_done = True;

        if not test_done:
            raise error.TestFail('Detect neither GL nor GLES')

        # Check X11 extensions.
        self.error_message = ""
        check_result = self.__check_x_extensions(result)
        if not check_result:
            raise error.TestFail('X extensions insufficient:' +
                                 self.error_message)
