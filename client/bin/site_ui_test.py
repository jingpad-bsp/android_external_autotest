# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import utils
from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_login, test as bin_test
from autotest_lib.client.common_lib import error, site_ui


class UITest(bin_test.test):
    """Base class for tests that drive some portion of the user interface.

    By default subclasses will use the default remote credentials before
    the run_once method is invoked, and will log out at the completion
    of the test case even if an exception is thrown.

    Subclasses can opt out of the automatic login by setting the member
    variable 'auto_login' to False.

    Subclasses can log in with arbitrary credentials by passing
    the 'creds' parameter in their control file.  See the documentation of
    UITest.initialize for more details.

    If your subclass overrides the initialize() or cleanup() methods, it
    should make sure to invoke this class' version of those methods as well.
    The standard super(...) function cannot be used for this, since the base
    test class is not a 'new style' Python class.
    """
    version = 1

    auto_login = True
    username = None
    password = None

    ca_cert_nickname = 'FakeCA'

    def __is_screensaver(self, status):
        """Returns True if xscreensaver reports a matching status.

        This function matches the output of `xscreensaver -time` against the
        specified status.  It does no sanity checking or framing of the status
        value, so use with caution.

        Args:
            status: String representing the status to match against.
        """
        return self.xsystem('xscreensaver-command -time | ' +
                            'egrep -q "%s"' % status, ignore_status=True) == 0


    def is_screensaver_locked(self):
        """Returns True if the screensaver is locked, false otherwise.

        The screensaver has more than two potential states, do not assume
        that the screensaver is completely deactivated if this returns False,
        use is_screensaver_unlocked() for that.
        """
        return self.__is_screensaver('locked|no saver status')


    def is_screensaver_unlocked(self):
        """Returns True if the screensaver is unlocked, false otherwise.

        The screensaver has more than two potential states, do not assume
        that the screensaver is completely locked if this returns False,
        use is_screensaver_locked() for that.
        """
        return self.__is_screensaver('non-blanked')


    def xsystem(self, cmd, timeout=None, ignore_status=False):
        """Convenience wrapper around site_ui.xsystem, to save you an import.
        """
        return site_ui.xsystem(cmd, timeout, ignore_status)


    def wait_for_screensaver(self, timeout=site_login._DEFAULT_TIMEOUT):
        """Convenience wrapper around site_login.wait_for_screensaver, to save
        you an import.
        """
        site_login.wait_for_screensaver(timeout=timeout)


    def initialize(self, creds='$default'):
        """Overridden from test.initialize() to log out and (maybe) log in.

        If self.auto_login is True, this will automatically log in using the
        credentials specified by 'creds' at startup, otherwise login will not
        happen.

        Regardless of the state of self.auto_login, the self.username and
        self.password properties will be set to the credentials specified
        by 'creds'.

        Args:
            creds: String specifying the credentials for this test case.  Can
                be a named set of credentials as defined by
                chromeos_constants.CREDENTIALS, or a 'username:password' pair.
                Defaults to '$default'.
        """
        if site_login.logged_in():
            site_login.attempt_logout()

        (self.username, self.password) = self.__resolve_creds(creds)

        if self.auto_login:
            self.login(self.username, self.password)


    def __resolve_creds(self, creds):
        if creds[0] == '$':
            if creds not in chromeos_constants.CREDENTIALS:
                raise error.TestFail('Unknown credentials: %s' % creds)

            return chromeos_constants.CREDENTIALS[creds]

        return creds.split(':')


    def login(self, username=None, password=None):
        """Log in with a set of credentials.

        Args:
            username: String representing the username to log in as, defaults
                to self.username.
            password: String representing the password to log in with, defaults
                to self.password.

        This method is called from UITest.initialize(), so you won't need it
        unless your testcase has cause to log in multiple times.  This
        DOES NOT affect self.username or self.password.

        Forces a log out if the test is already logged in.

        Raises:
            Exceptions raised by site_login.attempt_login
        """

        if site_login.logged_in():
            site_login.attempt_logout(timeout=site_login._DEFAULT_TIMEOUT)

        site_login.attempt_login(username or self.username,
                                 password or self.password)


    def logout(self):
        """Log out.

        This method is called from UITest.cleanup(), so you won't need it
        unless your testcase needs to test functionality while logged out.
        """
        site_login.attempt_logout()


    def get_autox(self):
        """Return a new autox instance.

        Explicitly cache this in your testcase if you want to reuse the
        object, but beware that logging out will invalidate any existing
        sessions.
        """
        return site_ui.get_autox()

    def cleanup(self):
        """Overridden from test.cleanup() to log out when the test is complete.
        """
        if site_login.logged_in():
            self.logout()
