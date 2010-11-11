# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, os, re, shutil, socket, sys, time
from autotest_lib.client.bin import chromeos_constants, site_cryptohome
from autotest_lib.client.bin import site_login, site_utils, test as bin_test
from autotest_lib.client.bin import site_log_reader
from autotest_lib.client.common_lib import error, site_ui
from autotest_lib.client.common_lib import site_auth_server, site_dns_server
from dbus.mainloop.glib import DBusGMainLoop

sys.path.append(os.environ.get("SYSROOT", "/usr/local") +
                "/usr/lib/flimflam/test")
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

    """Processes that we know crash and are willing to ignore."""
    crash_blacklist = ['powerm']

    def __init__(self, job, bindir, outputdir):
        self._dns = {}  # for saving/restoring dns entries
        bin_test.test.__init__(self, job, bindir, outputdir)

    def xsystem(self, cmd, timeout=None, ignore_status=False):
        """Convenience wrapper around site_ui.xsystem, to save you an import.
        """
        return site_ui.xsystem(cmd, timeout, ignore_status)

    def listen_to_signal(self, callback, signal, interface):
        """Listens to the given |signal| that is sent to power manager.
        """
        self._system_bus.add_signal_receiver(
            handler_function=callback,
            signal_name=signal,
            dbus_interface=interface,
            bus_name=None,
            path='/')

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
        self._bus_loop = DBusGMainLoop(set_as_default=True)
        self._system_bus = dbus.SystemBus(mainloop=self._bus_loop)
        self._flim = flimflam.FlimFlam(self._system_bus)
        for device in self._flim.GetObjectList('Device'):
            properties = device.GetProperties()
            interface = properties['Interface']
            logging.debug("Considering " + interface)
            for path in properties['IPConfigs']:
                ipconfig = self._flim.GetObjectInterface('IPConfig', path)

                servers = ipconfig.GetProperties().get('NameServers', None)
                if servers != None:
                    self._dns[path] = ','.join(servers)
                    logging.debug("Stored DNS for "  + interface)
                ipconfig.SetProperty('NameServers', '127.0.0.1')
                logging.debug("Using local DNS for "  + interface)

        site_utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com', '127.0.0.1'),
            site_login.TimeoutError('Timed out waiting for DNS changes.'),
            10)


    def revert_dns(self):
        """Clear the custom DNS setting for all devices and force them to use
        DHCP to pull the network's real settings again.
        """
        for device in self._flim.GetObjectList('Device'):
            properties = device.GetProperties()
            interface = properties['Interface']
            logging.debug("Considering " + interface)
            for path in properties['IPConfigs']:
                if path in self._dns:
                    ipconfig = self._flim.GetObjectInterface('IPConfig', path)
                    ipconfig.SetProperty('NameServers', self._dns[path])
                    logging.debug("Reverted DNS for "  + interface)
                else:
                    logging.debug("No stored DNS for " + interface)

        site_utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com',
                                           '127.0.0.1',
                                           expected=False),
            site_login.TimeoutError('Timed out waiting to revert DNS.'),
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

        # Mark /var/log/messages now; we'll run through all subsequent
        # log messages at the end of the test and log info about processes that
        # crashed.
        self._log_reader = site_log_reader.LogReader()
        self._log_reader.set_start_by_current()

        self.start_authserver()

        if site_login.logged_in():
            site_login.attempt_logout()

        (self.username, self.password) = self.__resolve_creds(creds)
        # Ensure there's no stale cryptohome from previous tests.
        try:
            site_cryptohome.remove_vault(self.username)
        except site_cryptohome.ChromiumOSError, error:
            logging.error(error)
        # Ensure there's no stale owner state from previous tests.
        try:
            os.unlink(chromeos_constants.OWNER_KEY_FILE)
            os.unlink(chromeos_constants.SIGNED_PREFERENCES_FILE)
        except (IOError, OSError) as error:
            logging.info(error)
        site_login.refresh_login_screen()

        if self.auto_login:
            self.login(self.username, self.password)


    def __canonicalize(self, credential):
        """Perform basic canonicalization of |email_address|

        Perform basic canonicalization of |email_address|, taking
        into account that gmail does not consider '.' or caps inside a
        username to matter.  It also ignores everything after a '+'.
        For example, c.masone+abc@gmail.com == cMaSone@gmail.com, per
        http://mail.google.com/support/bin/answer.py?hl=en&ctx=mail&answer=10313
        """
        parts = credential.split('@')
        if len(parts) != 2:
          raise error.TestError("Malformed email: " + credential)

        (name, domain) = parts
        name = name.partition('+')[0].replace('.', '')
        return '@'.join([name, domain]).lower()


    def __resolve_creds(self, creds):
        if creds[0] == '$':
            if creds not in chromeos_constants.CREDENTIALS:
                raise error.TestFail('Unknown credentials: %s' % creds)

            (name, passwd) = chromeos_constants.CREDENTIALS[creds]
            return [self.__canonicalize(name), passwd]

        (name, passwd) = creds.split(':')
        return [self.__canonicalize(name), passwd]


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
            site_login.refresh_login_screen()

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


    def __log_crashed_processes(self, processes):
        """Runs through the log watched by |watcher| to see if a crash was
        reported for any process names listed in |processes|.
        """
        regex = re.compile(r'Received crash notification for (\w+).+ (sig \d+)',
                           re.MULTILINE)
        for match in regex.finditer(self._log_reader.get_logs()):
            if match.group(1) in processes:
                self.job.record('INFO', self.tagged_testname,
                                "%s crash" % m.group(1), m.group(2))


    def cleanup(self):
        """Overridden from test.cleanup() to log out when the test is complete.
        """
        logpath = chromeos_constants.CHROME_LOG_DIR

        try:
            for file in os.listdir(logpath):
                fullpath = os.path.join(logpath, file)
                if os.path.isfile(fullpath):
                    shutil.copy(fullpath, os.path.join(self.resultsdir, file))

        except (IOError, OSError) as error:
            logging.error(error)

        if site_login.logged_in():
            try:
                shutil.copy(chromeos_constants.CRYPTOHOME_MOUNT_PT+'/chrome',
                            self.resultsdir+'/chrome_postlogin_log')
            except (IOError, OSError) as error:
                logging.error(error)
            self.logout()

        if os.path.isfile(chromeos_constants.CRYPTOHOMED_LOG):
            try:
                base = os.path.basename(chromeos_constants.CRYPTOHOMED_LOG)
                shutil.copy(chromeos_constants.CRYPTOHOMED_LOG,
                            os.path.join(self.resultsdir, base))
            except (IOError, OSError) as error:
                logging.error(error)

        self.stop_authserver()
        self.__log_crashed_processes(self.crash_blacklist)


    def get_auth_endpoint_misses(self):
        if hasattr(self, '_authServer'):
            return self._authServer.get_endpoint_misses()
        else:
            return {}
