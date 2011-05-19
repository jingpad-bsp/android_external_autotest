# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, os, re, shutil, socket, sys
import common
import auth_server, constants, cryptohome, dns_server
import cros_logging, cros_ui, login, ownership
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from dbus.mainloop.glib import DBusGMainLoop

from autotest_lib.client.cros import flimflam_test_path
import flimflam


class UITest(test.test):
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
    fake_owner = True
    username = None
    password = None

    # Processes that we know crash and are willing to ignore.
    crash_blacklist = []

    def __init__(self, job, bindir, outputdir):
        self._dns = {}  # for saving/restoring dns entries
        test.test.__init__(self, job, bindir, outputdir)

    def xsystem(self, cmd, timeout=None, ignore_status=False):
        """Convenience wrapper around cros_ui.xsystem, to save you an import.
        """
        return cros_ui.xsystem(cmd, timeout, ignore_status)

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
            host = socket.gethostbyname(hostname)
            logging.debug("Resolve attempt for %s got %s" % (hostname, host))
            return (host == ip) == expected
        except socket.gaierror as err:
            logging.error(err)

    def use_local_dns(self, dns_port=53):
        """Set all devices to use our in-process mock DNS server.
        """
        self._dnsServer = dns_server.LocalDns(local_port=dns_port)
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
                    logging.debug("Stored %s for %s" % (self._dns[path],
                                                        interface))
                ipconfig.SetProperty('NameServers', '127.0.0.1')
                logging.debug("Using local DNS for " + interface)

        utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com', '127.0.0.1'),
            login.TimeoutError('Timed out waiting for DNS changes.'),
            timeout=10,
            sleep_interval=1)


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
                    logging.debug("Reverted DNS for " + interface)
                else:
                    logging.debug("No stored DNS for " + interface)

        utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com',
                                           '127.0.0.1',
                                           expected=False),
            login.TimeoutError('Timed out waiting to revert DNS.'),
            10)


    def start_authserver(self):
        """Spin up a local mock of the Google Accounts server, then spin up
        a local fake DNS server and tell the networking stack to use it.  This
        will trick Chrome into talking to our mock when we login.
        Subclasses can override this method to change this behavior.
        """
        self._authServer = auth_server.GoogleAuthServer()
        self._authServer.run()
        self.use_local_dns()


    def initialize(self, creds=None, is_creating_owner=False):
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
                constants.CREDENTIALS, or a 'username:password' pair.
                Defaults to None -- browse without signing-in.
            is_creating_owner: If the test case is creating a new device owner.

        """

        # Mark /var/log/messages now; we'll run through all subsequent
        # log messages at the end of the test and log info about processes that
        # crashed.
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        if creds:
            self.start_authserver()

        if login.logged_in():
            login.attempt_logout()

        # The UI must be taken down to ensure that no stale state persists.
        cros_ui.stop()
        (self.username, self.password) = self.__resolve_creds(creds)
        # Ensure there's no stale cryptohome from previous tests.
        try:
            cryptohome.remove_vault(self.username)
        except cryptohome.ChromiumOSError as err:
            logging.error(err)

        # Fake ownership unless the test is explicitly testing owner creation.
        if not is_creating_owner:
            logging.info('Faking ownership...')
            self.__fake_ownership()
            self.fake_owner = True
        else:
            logging.info('Erasing stale owner state.')
            ownership.clear_ownership()
            self.fake_owner = False
        cros_ui.start()

        login.refresh_login_screen()
        if self.auto_login:
            self.login(self.username, self.password)
            if is_creating_owner:
                login.wait_for_ownership()

    def __fake_ownership(self):
        """Fake ownership by generating the necessary magic files."""
        # Determine the module directory.
        dirname = os.path.dirname(__file__)
        mock_certfile = os.path.join(dirname, constants.MOCK_OWNER_CERT)
        mock_signedpolicyfile = os.path.join(dirname,
                                             constants.MOCK_OWNER_POLICY)
        utils.open_write_close(
            constants.OWNER_KEY_FILE,
            ownership.cert_extract_pubkey_der(mock_certfile))
        shutil.copy(mock_signedpolicyfile,
                    constants.SIGNED_POLICY_FILE)


    def __canonicalize(self, credential):
        """Perform basic canonicalization of |email_address|

        Perform basic canonicalization of |email_address|, taking
        into account that gmail does not consider '.' or caps inside a
        username to matter.  It also ignores everything after a '+'.
        For example, c.masone+abc@gmail.com == cMaSone@gmail.com, per
        http://mail.google.com/support/bin/answer.py?hl=en&ctx=mail&answer=10313
        """
        if not credential:
          return None

        parts = credential.split('@')
        if len(parts) != 2:
          raise error.TestError("Malformed email: " + credential)

        (name, domain) = parts
        name = name.partition('+')[0]
        if (domain == constants.SPECIAL_CASE_DOMAIN):
            name = name.replace('.', '')
        return '@'.join([name, domain]).lower()


    def __resolve_creds(self, creds):
        """Map credential identifier to username, password and type.
        Args:
          creds: credential identifier to resolve.

        Returns:
          A (username, password) tuple.
        """
        if not creds:
            return [None, None]  # Browse without signing-in.
        if creds[0] == '$':
            if creds not in constants.CREDENTIALS:
                raise error.TestFail('Unknown credentials: %s' % creds)

            (name, passwd) = constants.CREDENTIALS[creds]
            return [self.__canonicalize(name), passwd]

        (name, passwd) = creds.split(':')
        return [self.__canonicalize(name), passwd]


    def ensure_login_complete(self):
        """Wait for authentication to complete.  If you want a different
        termination condition, override this method.
        """
        if hasattr(self, '_authServer'):
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
            Exceptions raised by login.attempt_login
        """
        if login.logged_in():
            login.attempt_logout(timeout=login._DEFAULT_TIMEOUT)
            login.refresh_login_screen()

        login.attempt_login(username or self.username,
                            password or self.password)
        self.ensure_login_complete()


    def logout(self):
        """Log out.

        This method is called from UITest.cleanup(), so you won't need it
        unless your testcase needs to test functionality while logged out.
        """
        login.attempt_logout()


    def get_autox(self):
        """Return a new autox instance.

        Explicitly cache this in your testcase if you want to reuse the
        object, but beware that logging out will invalidate any existing
        sessions.
        """
        return cros_ui.get_autox()


    def validate_basic_policy(self, basic_policy):
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from device_management_backend_pb2 import PolicyFetchResponse
        from device_management_backend_pb2 import PolicyData
        from chrome_device_policy_pb2 import ChromeDeviceSettingsProto
        from chrome_device_policy_pb2 import UserWhitelistProto

        response_proto = PolicyFetchResponse()
        response_proto.ParseFromString(basic_policy)
        ownership.assert_has_policy_data(response_proto)

        poldata = PolicyData()
        poldata.ParseFromString(response_proto.policy_data)
        ownership.assert_has_device_settings(poldata)
        ownership.assert_username(poldata, self.username)

        polval = ChromeDeviceSettingsProto()
        polval.ParseFromString(poldata.policy_value)
        ownership.assert_new_users(polval, True)
        ownership.assert_users_on_whitelist(polval, (self.username,))


    def stop_authserver(self):
        """Tears down fake dns and fake Google Accounts server.  If your
        subclass does not create these objects, you will want to override this
        method as well.
        """
        if hasattr(self, '_authServer'):
            self.revert_dns()
            self._authServer.stop()
            self._dnsServer.stop()


    def __log_crashed_processes(self, processes):
        """Runs through the log watched by |watcher| to see if a crash was
        reported for any process names listed in |processes|. SIGABRT crashes in
        chrome or supplied-chrome during logout are ignored.
        """
        logout_start_regex = re.compile(login.LOGOUT_ATTEMPT_MSG)
        crash_regex = re.compile(
            'Received crash notification for ([-\w]+).+ (sig \d+)')
        logout_complete_regex = re.compile(login.LOGOUT_COMPLETE_MSG)

        in_logout = False
        for line in self._log_reader.get_logs().splitlines():
            if logout_start_regex.search(line):
                in_logout = True
            elif logout_complete_regex.search(line):
                in_logout = False
            else:
                match = crash_regex.search(line)
                if (match and not match.group(1) in processes and
                    not (in_logout and
                         (match.group(1) == constants.BROWSER or
                          match.group(1) == 'supplied_chrome') and
                         match.group(2) == 'sig 6')):
                    self.job.record('INFO', self.tagged_testname,
                                    line[match.start():])


    def cleanup(self):
        """Overridden from test.cleanup() to log out when the test is complete.
        """
        logpath = constants.CHROME_LOG_DIR

        try:
            for filename in os.listdir(logpath):
                fullpath = os.path.join(logpath, filename)
                if os.path.isfile(fullpath):
                    shutil.copy(fullpath, os.path.join(self.resultsdir,
                                                       filename))

        except (IOError, OSError) as err:
            logging.error(err)

        if login.logged_in():
            try:
                # Recover dirs from cryptohome in case another test run wipes.
                for dir in constants.CRYPTOHOME_DIRS_TO_RECOVER:
                    dir_path = os.path.join(constants.CRYPTOHOME_MOUNT_PT, dir)
                    if os.path.isdir(dir_path):
                        shutil.copytree(
                            dir_path, os.path.join(self.resultsdir, dir))
            except (IOError, OSError) as err:
                logging.error(err)
            self.logout()

        if os.path.isfile(constants.CRYPTOHOMED_LOG):
            try:
                base = os.path.basename(constants.CRYPTOHOMED_LOG)
                shutil.copy(constants.CRYPTOHOMED_LOG,
                            os.path.join(self.resultsdir, base))
            except (IOError, OSError) as err:
                logging.error(err)

        if self.fake_owner:
            logging.info('Erasing fake owner state.')
            ownership.clear_ownership()

        self.stop_authserver()
        self.__log_crashed_processes(self.crash_blacklist)


    def get_auth_endpoint_misses(self):
        if hasattr(self, '_authServer'):
            return self._authServer.get_endpoint_misses()
        else:
            return {}
