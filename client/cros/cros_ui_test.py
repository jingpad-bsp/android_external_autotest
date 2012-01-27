# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, glob, logging, os, re, shutil, socket, stat, subprocess, sys, time
import auth_server, constants, cryptohome, dns_server
import cros_logging, cros_ui, login, ownership, pyauto_test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from dbus.mainloop.glib import DBusGMainLoop

from autotest_lib.client.cros import flimflam_test_path
import flimflam


class UITest(pyauto_test.PyAutoTest):
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

    # This is a symlink.  We look up the real path at runtime by following it.
    _resolv_test_file = 'resolv.conf.test'
    _resolv_bak_file = 'resolv.conf.bak'

    def __init__(self, job, bindir, outputdir):
        pyauto_test.PyAutoTest.__init__(self, job, bindir, outputdir)


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


    def __connect_to_flimflam(self):
        """Connect to the network manager via DBus.

        Stores dbus connection in self._flim upon success, throws on failure.
        """
        self._bus_loop = DBusGMainLoop(set_as_default=True)
        self._system_bus = dbus.SystemBus(mainloop=self._bus_loop)
        self._flim = flimflam.FlimFlam(self._system_bus)


    def __get_host_by_name(self, hostname):
        """Resolve the dotted-quad IPv4 address of |hostname|

        This used to use suave python code, like this:
            hosts = socket.getaddrinfo(hostname, 80, socket.AF_INET)
            (fam, socktype, proto, canonname, (host, port)) = hosts[0]
            return host

        But that hangs sometimes, and we don't understand why.  So, use
        a subprocess with a timeout.
        """
        try:
            host = utils.system_output('%s -c "import socket; '
                                       'print socket.gethostbyname(\'%s\')"' % (
                                       sys.executable, hostname),
                                       ignore_status=True, timeout=2)
        except Exception as e:
            logging.warning(e)
            return None
        return host or None


    def __attempt_resolve(self, hostname, ip, expected=True):
        logging.debug('Attempting to resolve %s to %s' % (hostname, ip))
        try:
            host = self.__get_host_by_name(hostname)
            logging.debug('Resolve attempt for %s got %s' % (hostname, host))
            return host and (host == ip) == expected
        except socket.gaierror as err:
            logging.error(err)


    def use_local_dns(self, dns_port=53):
        """Set all devices to use our in-process mock DNS server.
        """
        self._dnsServer = dns_server.LocalDns(fake_ip='127.0.0.1',
                                              local_port=dns_port)
        self._dnsServer.run()
        # Turn off captive portal checking, until we fix
        # http://code.google.com/p/chromium-os/issues/detail?id=19640
        self.check_portal_list = self._flim.GetCheckPortalList()
        self._flim.SetCheckPortalList('')
        # Set all devices to use locally-running DNS server.
        try:
            # Follow resolv.conf symlink.
            resolv = os.path.realpath(constants.RESOLV_CONF_FILE)
            # Grab path to the real file, do following work in that directory.
            resolv_dir = os.path.dirname(resolv)
            resolv_test = os.path.join(resolv_dir, self._resolv_test_file)
            resolv_bak = os.path.join(resolv_dir, self._resolv_bak_file)
            resolv_contents = 'nameserver 127.0.0.1'
            # Back up the current resolv.conf.
            os.rename(resolv, resolv_bak)
            # To stop flimflam from editing resolv.conf while we're working
            # with it, we want to make the directory -r-x-r-x-r-x.  Open an
            # fd to the file first, so that we'll retain the ability to
            # alter it.
            resolv_fd = open(resolv, 'w')
            self._resolv_dir_mode = os.stat(resolv_dir).st_mode
            os.chmod(resolv_dir, (stat.S_IRUSR | stat.S_IXUSR |
                                  stat.S_IRGRP | stat.S_IXGRP |
                                  stat.S_IROTH | stat.S_IXOTH))
            resolv_fd.write(resolv_contents)
            resolv_fd.close()
            assert utils.read_one_line(resolv) == resolv_contents
        except Exception as e:
            logging.error(str(e))
            raise e

        utils.poll_for_condition(
            lambda: self.__attempt_resolve('www.google.com.', '127.0.0.1'),
            utils.TimeoutError('Timed out waiting for DNS changes.'),
            timeout=10)


    def revert_dns(self):
        """Clear the custom DNS setting for all devices and force them to use
        DHCP to pull the network's real settings again.
        """
        try:
            # Follow resolv.conf symlink.
            resolv = os.path.realpath(constants.RESOLV_CONF_FILE)
            # Grab path to the real file, do following work in that directory.
            resolv_dir = os.path.dirname(resolv)
            resolv_bak = os.path.join(resolv_dir, self._resolv_bak_file)
            os.chmod(resolv_dir, self._resolv_dir_mode)
            os.rename(resolv_bak, resolv)

            utils.poll_for_condition(
                lambda: self.__attempt_resolve('www.google.com.',
                                               '127.0.0.1',
                                               expected=False),
                utils.TimeoutError('Timed out waiting to revert DNS.'),
                timeout=10)
        finally:
            # Set captive portal checking to whatever it was at the start.
            self._flim.SetCheckPortalList(self.check_portal_list)


    def start_authserver(self):
        """Spin up a local mock of the Google Accounts server, then spin up
        a local fake DNS server and tell the networking stack to use it.  This
        will trick Chrome into talking to our mock when we login.
        Subclasses can override this method to change this behavior.
        """
        self._authServer = auth_server.GoogleAuthServer()
        self._authServer.run()
        self.use_local_dns()


    def stop_authserver(self):
        """Tears down fake dns and fake Google Accounts server.  If your
        subclass does not create these objects, you will want to override this
        method as well.
        """
        if hasattr(self, '_authServer'):
            self.revert_dns()
            self._authServer.stop()
            self._dnsServer.stop()


    class Tcpdump(object):
        """Run tcpdump and save output.

        To be used with 'with' statement.
        """
        # Handle to tcpdump process.
        _tcpdump = None

        def __init__(self, iface, fname_prefix, results_dir):
            self._iface = iface
            self._fname_prefix = fname_prefix
            self._results_dir = results_dir


        def __enter__(self):
            self._tcpdump = subprocess.Popen(
                ['tcpdump', '-i', self._iface, '-vv'], stdout=subprocess.PIPE)


        def __exit__(self, type, value, traceback):
            """Stop tcpdump process and save output to a new file."""
            if not self._tcpdump:
                return
            self._tcpdump.terminate()
            # Save output to a new file
            next_index = len(glob.glob(
                os.path.join(self._results_dir, '%s-*' % self._fname_prefix)))
            tcpdump_file = os.path.join(
                self._results_dir, '%s-%d' % (self._fname_prefix, next_index))
            logging.info('Saving tcpdump output to %s.' % tcpdump_file)
            open(tcpdump_file, 'w').write(self._tcpdump.communicate()[0])


    def initialize(self, creds=None, is_creating_owner=False,
                   extra_chrome_flags=[]):
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
            extra_chrome_flags: Extra chrome flags to pass to chrome, if any.

        """
        # Mark /var/log/messages now; we'll run through all subsequent
        # log messages at the end of the test and log info about processes that
        # crashed.
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        self.__connect_to_flimflam()

        if creds:
            self.start_authserver()

        # We yearn for Chrome coredumps...
        open(constants.CHROME_CORE_MAGIC_FILE, 'w').close()

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

        pyauto_test.PyAutoTest.initialize(self, auto_login=False,
                                          extra_chrome_flags=extra_chrome_flags)
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
            return [cryptohome.canonicalize(name), passwd]

        (name, passwd) = creds.split(':')
        return [cryptohome.canonicalize(name), passwd]


    def __take_screenshot(self, fname_prefix):
      """Take screenshot and save to a new file in the results dir.

      Args:
        fname_prefix: prefix for the output fname
      """
      next_index = len(glob.glob(
          os.path.join(self.resultsdir, '%s-*.png' % fname_prefix)))
      screenshot_file = os.path.join(
          self.resultsdir, '%s-%d.png' % (fname_prefix, next_index))
      logging.info('Saving screenshot to %s.' % screenshot_file)
      utils.system('DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority '
                   'screenshot %s' % screenshot_file)


    def login(self, username=None, password=None):
        """Log in with a set of credentials.

        This method is called from UITest.initialize(), so you won't need it
        unless your testcase has cause to log in multiple times.  This
        DOES NOT affect self.username or self.password.

        If username and self.username are not defined, logs in as guest.

        Forces a log out if already logged in.
        Blocks until login is complete.

        TODO(nirnimesh): Does NOT work with webui login
                         crosbug.com/18271

        Args:
            username: username to log in as, defaults to self.username.
            password: password to log in with, defaults to self.password.

        Raises:
            error.TestError, if login has an error
        """
        if self.logged_in():
            self.logout()

        uname = username or self.username
        passwd = password or self.password

        # Run tcpdump on 'lo' interface to investigate network
        # issues in the lab during login.
        with UITest.Tcpdump(iface='lo', fname_prefix='tcpdump-lo-login',
                            results_dir=self.resultsdir):
            try:
                if uname:  # Regular login
                    login_error = self.pyauto.Login(username=uname,
                                                    password=passwd)
                    if login_error:
                        raise error.TestError(
                            'Error during login (%s, %s): %s.' % (
                            uname, passwd, login_error))
                    logging.info('Logged in as %s.' % uname)
                else:  # Login as guest
                    self.pyauto.LoginAsGuest()
                    logging.info('Logged in as guest.')
            except:
                self.__take_screenshot(fname_prefix='login-fail-screenshot')
                raise

        if not self.logged_in():
            raise error.TestError('Not logged in')


    def logged_in(self):
        return self.pyauto.GetLoginInfo()['is_logged_in']


    def logout(self):
        """Log out.

        This method is called from UITest.cleanup(), so you won't need it
        unless your testcase needs to test functionality while logged out.
        """
        if not self.logged_in():
            return
        self._save_logs_from_cryptohome()
        cros_ui.restart(self.pyauto.Logout)


    def _save_logs_from_cryptohome(self):
        """Recover dirs from cryptohome in case another test run wipes."""
        try:
            for dir in constants.CRYPTOHOME_DIRS_TO_RECOVER:
                dir_path = os.path.join(constants.CRYPTOHOME_MOUNT_PT, dir)
                if os.path.isdir(dir_path):
                    target = os.path.join(self.resultsdir,
                                          '%s-%f' % (dir, time.time()))
                    logging.debug('Saving %s to %s.', dir_path, target)
                    shutil.copytree(src=dir_path, dst=target, symlinks=True)
        except (IOError, OSError, shutil.Error) as err:
            logging.error(err)


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


    def __log_crashed_processes(self, processes):
        """Runs through the log watched by |watcher| to see if a crash was
        reported for any process names listed in |processes|. SIGABRT crashes in
        chrome or supplied-chrome during ui restart are ignored.
        """
        ui_restart_begin_regex = re.compile(cros_ui.UI_RESTART_ATTEMPT_MSG)
        crash_regex = re.compile(
            'Received crash notification for ([-\w]+).+ (sig \d+)')
        ui_restart_end_regex = re.compile(cros_ui.UI_RESTART_COMPLETE_MSG)

        in_restart = False
        for line in self._log_reader.get_logs().splitlines():
            if ui_restart_begin_regex.search(line):
                in_restart = True
            elif ui_restart_end_regex.search(line):
                in_restart = False
            else:
                match = crash_regex.search(line)
                if (match and not match.group(1) in processes and
                    not (in_restart and
                         (match.group(1) == constants.BROWSER or
                          match.group(1) == 'supplied_chrome') and
                         match.group(2) == 'sig 6')):
                    self.job.record('INFO', self.tagged_testname,
                                    line[match.start():])


    def cleanup(self):
        """Overridden from pyauto_test.cleanup() to log out and restart
           session_manager when the test is complete.
        """
        try:
            logpath = constants.CHROME_LOG_DIR
            try:
                for filename in os.listdir(logpath):
                    fullpath = os.path.join(logpath, filename)
                    if os.path.isfile(fullpath):
                        shutil.copy(fullpath, os.path.join(self.resultsdir,
                                                           filename))
            except (IOError, OSError) as err:
                logging.error(err)

            self._save_logs_from_cryptohome()
            pyauto_test.PyAutoTest.cleanup(self)

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

            self.__log_crashed_processes(self.crash_blacklist)

            if os.path.isfile(constants.CHROME_CORE_MAGIC_FILE):
                os.unlink(constants.CHROME_CORE_MAGIC_FILE)
        finally:
            self.stop_authserver()


    def get_auth_endpoint_misses(self):
        if hasattr(self, '_authServer'):
            return self._authServer.get_endpoint_misses()
        else:
            return {}
