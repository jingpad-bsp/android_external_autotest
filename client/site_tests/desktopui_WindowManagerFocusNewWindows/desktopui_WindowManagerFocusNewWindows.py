# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import cros_ui, cros_ui_test, login

class desktopui_WindowManagerFocusNewWindows(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        cros_ui_test.UITest.initialize(self, creds)

    def run_once(self):
        autox = cros_ui.get_autox()
        autox.await_condition(
            lambda: autox.get_active_window_property(),
            desc='Waiting for _NET_ACTIVE_WINDOW to be set');
