# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import session_manager
from autotest_lib.client.cros import cros_ui, cryptohome


class login_SameSessionTwice(test.test):
    """Ensure that the session_manager won't start the same session twice.
    """
    version = 1


    def initialize(self):
        super(login_SameSessionTwice, self).initialize()
        cros_ui.restart()


    def run_once(self):
        sm = session_manager.connect()

        user = 'first_user@nowhere.com'
        cryptohome.ensure_clean_cryptohome_for(user)

        if not sm.StartSession(user, ''):
            raise error.TestFail('Could not start session for ' + user)

        try:
            if sm.StartSession(user, ''):
                raise error.TestFail('Started second session for ' + user)
        except dbus.DBusException as d:
            # If I knew how to get our custom dbus errors mapped into real
            # exceptions in PyDBus, I'd use that here :-/
            if 'already started a session' not in d.message:
                raise error.TestFail(d)


    def cleanup(self):
        cros_ui.start(allow_fail=True, wait_for_login_prompt=False)
