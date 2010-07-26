# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, os, shutil, socket, sys, time
from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_login, site_utils, test as bin_test
from autotest_lib.client.common_lib import error, site_ui
from autotest_lib.client.common_lib import site_auth_server, site_dns_server

# Workaround so flimflam.py doesn't need to be installed in the chroot.
sys.path.append(os.environ.get('SYSROOT', '') + '/usr/lib/flimflam/test')
# NB: /usr/local is temporary for compatibility
sys.path.append(os.environ.get('SYSROOT', '') + '/usr/local/lib/flimflam/test')
import flimflam


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

    def __init__(self, job, bindir, outputdir):
        self._dns = {}  # for saving/restoring dns entries
        bin_test.test.__init__(self, job, bindir, outputdir)

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


    def __attempt_resolve(self, hostname, ip, expected=True):
        try:
            return (socket.gethostbyname(hostname) == ip) == expected
        except socket.gaierror, error:
            logging.error(error)


    def use_local_dns(self, dns_port=53):
        """Set all devices to use our in-process mock DNS server.
        """
        self._dnsServer = site_dns_server.LocalDns(local_port=dns_port)
        self._dnsServer.run()

        self._flim = flimflam.FlimFlam(dbus.SystemBus())
        for device in self._flim.GetObjectList('Device'):
            properties = device.GetProperties()
            for path in properties['IPConfigs']:
                ipconfig = self._flim.GetObjectInterface('IPConfig', path)

                servers = ipconfig.GetProperties().get('NameServers', None)
                if servers != None:
                  self._dns[path] = ','.join(servers)
                ipconfig.SetProperty('NameServers', '127.0.0.1')

        site_utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com', '127.0.0.1'),
            site_login.TimeoutError('Timed out waiting for DNS changes.'),
            10)
        site_login.refresh_login_screen()


    def revert_dns(self):
        """Clear the custom DNS setting for all devices and force them to use
        DHCP to pull the network's real settings again.
        """
        for device in self._flim.GetObjectList('Device'):
            properties = device.GetProperties()
            for path in properties['IPConfigs']:
                ipconfig = self._flim.GetObjectInterface('IPConfig', path)
                ipconfig.SetProperty('NameServers', self._dns[path])

        site_utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com',
                                           '127.0.0.1',
                                           expected=False),
            site_login.TimeoutError('Timed out waiting for DNS changes.'),
            10)


    def start_authserver(self):
        """Spin up a local mock of the Google Accounts server, then spin up
        a locak fake DNS server and tell the networking stack to use it.  This
        will trick Chrome into talking to our mock when we login.
        Subclasses can override this method to change this behavior.
        """
        self._authServer = site_auth_server.GoogleAuthServer()
        self._authServer.run()
        self.use_local_dns()


    def initialize(self, creds='$default'):
        """Overridden from test.initialize() to log out and (maybe) log in.

        If self.auto_login is True, this will automatically log in using the
        credentials specified by 'creds' at startup, otherwise login will not
        happen.

        Regardless of the state of self.auto_login, the self.username and
        self.password properties will be set to the credentials specified
        by 'creds'.

        Authentication is not performed against live servers.  Instead, we spin
        up a local DNS server that will lie and say that all sites resolve to
        127.0.0.1.  We use DBus to tell flimflam to use this DNS server to
        resolve addresses.  We then spin up a local httpd that will respond
        to queries at the Google Accounts endpoints.  We clear the DNS setting
        and tear down these servers in cleanup().

        Args:
            creds: String specifying the credentials for this test case.  Can
                be a named set of credentials as defined by
                chromeos_constants.CREDENTIALS, or a 'username:password' pair.
                Defaults to '$default'.

        """
        self.start_authserver()

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


    def ensure_login_complete(self):
        """Wait for authentication to complete.  If you want a different
        termination condition, override this method.
        """
        self._authServer.wait_for_client_login()


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
        self.ensure_login_complete()



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


    def stop_authserver(self):
        """Tears down fake dns and fake Google Accounts server.  If your
        subclass does not create these objects, you will want to override this
        method as well.
        """
        self.revert_dns()
        self._authServer.stop()
        self._dnsServer.stop()


    def cleanup(self):
        """Overridden from test.cleanup() to log out when the test is complete.
        """
        shutil.copy(chromeos_constants.USER_DATA_DIR+'/chrome_log',
                    self.resultsdir+'/chrome_prelogin_log')
        if site_login.logged_in():
            shutil.copy(chromeos_constants.USER_DATA_DIR+'/user/chrome_log',
                        self.resultsdir+'/chrome_postlogin_log')
            self.logout()

        self.stop_authserver()
