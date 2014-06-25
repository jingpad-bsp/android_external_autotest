# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import chrome_binary_test
from autotest_lib.client.cros.graphics import graphics_utils

class graphics_GLES2ConformChrome(chrome_binary_test.ChromeBinaryTest):
    """
    Run the Khronos GLES2 Conformance test suite against the Chrome GPU command
    buffer.
    """
    version = 1
    GSC = None
    BINARY = 'gles2_conform_test'

    def initialize(self):
        super(graphics_GLES2ConformChrome, self).initialize()
        self.GSC = graphics_utils.GraphicsStateChecker()

    def cleanup(self):
        super(graphics_GLES2ConformChrome, self).cleanup()
        if self.GSC:
            self.GSC.finalize()

    def run_once(self):
        self.run_chrome_test_binary(self.BINARY)
