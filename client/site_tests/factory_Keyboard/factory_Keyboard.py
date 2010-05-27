# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate that all keyboard
# keys function properly.  This program will display a keyboard image
# and keys will be highlighted as they are pressed and released.
# After the first key is hit, a countdown will begin.  If not all keys
# are used in time, the test will fail.


from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import factory_test

import cairo
import os

import KeyboardTest


class factory_Keyboard(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None, layout=None):

        factory_test.XXX_log('factory_Keyboard')

        # XXX Why can this not be run from the UI code?
        xset_status = os.system('xset r off')
        xmm_status = os.system('xmodmap -e "clear Lock"')
        if xset_status or xmm_status:
            raise TestFail('ERROR: disabling key repeat or caps lock')

        factory_test.init(trigger_set=trigger_set,
                          result_file_path=result_file_path)

        os.chdir(self.srcdir)
        kbd_image = cairo.ImageSurface.create_from_png('%s.png' % layout)
        with open('%s.bindings' % layout, 'r') as file:
            bindings = eval(file.read())

        test_widget, wr_cb = KeyboardTest.make_test_widget(kbd_image, bindings)

        factory_test.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=wr_cb)
