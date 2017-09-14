# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os

from autotest_lib.client.common_lib import enum
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


"""
Error enum returned from almost all D-Bus calls.
See CrOS - platform/system_api/dbus/authpolicy/active_directory_info.proto.
KEEP THE ORDER IN SYNC WITH THE PROTO FILE!

"""
ErrorType = enum.Enum(
        'ERROR_NONE',                        # 0
        'ERROR_UNKNOWN',                     # 1
        'ERROR_DBUS_FAILURE',                # 3
        'ERROR_PARSE_UPN_FAILED',            # 4
        'ERROR_BAD_USER_NAME',               # 5
        'ERROR_BAD_PASSWORD',                # 6
        'ERROR_PASSWORD_EXPIRED',            # 7
        'ERROR_CANNOT_RESOLVE_KDC',          # 8
        'ERROR_KINIT_FAILED',                # 9
        'ERROR_NET_FAILED',                  # 10
        'ERROR_SMBCLIENT_FAILED',            # 11
        'ERROR_PARSE_FAILED',                # 12
        'ERROR_PARSE_PREG_FAILED',           # 13
        'ERROR_BAD_GPOS',                    # 14
        'ERROR_LOCAL_IO',                    # 15
        'ERROR_NOT_JOINED',                  # 16
        'ERROR_NOT_LOGGED_IN',               # 17
        'ERROR_STORE_POLICY_FAILED',         # 18
        'ERROR_JOIN_ACCESS_DENIED',          # 19
        'ERROR_NETWORK_PROBLEM',             # 19
        'ERROR_INVALID_MACHINE_NAME',        # 20
        'ERROR_MACHINE_NAME_TOO_LONG',       # 21
        'ERROR_USER_HIT_JOIN_QUOTA',         # 22
        'ERROR_CONTACTING_KDC_FAILED',       # 23
        'ERROR_NO_CREDENTIALS_CACHE_FOUND',  # 24
        'ERROR_KERBEROS_TICKET_EXPIRED',     # 25
        'ERROR_KLIST_FAILED',                # 26
        'ERROR_BAD_MACHINE_NAME',            # 27
        'ERROR_PASSWORD_REJECTED',           # 28
        'ERROR_COUNT')                       # 29


class AuthPolicy(object):
    """
    Wrapper for D-Bus calls ot the AuthPolicy daemon.

    The AuthPolicy daemon handles Active Directory domain join, user
    authentication and policy fetch. This class is a wrapper around the D-Bus
    interface to the daemon.

    """

    # Log file written by authpolicyd.
    _LOG_FILE = '/var/log/authpolicy.log'

    # Number of log lines to include in error logs.
    _LOG_LINE_LIMIT = 50

    # The usual system log file (minijail logs there!).
    _SYSLOG_FILE = '/var/log/messages'

    # Authpolicy daemon D-Bus parameters.
    _DBUS_SERVICE_NAME = 'org.chromium.AuthPolicy'
    _DBUS_SERVICE_PATH = '/org/chromium/AuthPolicy'
    _DBUS_INTERFACE_NAME = 'org.chromium.AuthPolicy'

    # Chronos user ID.
    _CHRONOS_UID = 1000

    def __init__(self, bus_loop):
        """
        Constructor

        Creates and returns a D-Bus connection to authpolicyd. The daemon must
        be running.

        @param bus_loop: glib main loop object.

        """

        try:
            # Get the interface as Chronos since only they are allowed to send
            # D-Bus messages to authpolicyd.
            os.setresuid(self._CHRONOS_UID, self._CHRONOS_UID, 0)
            bus = dbus.SystemBus(bus_loop)

            proxy = bus.get_object(self._DBUS_SERVICE_NAME,
                                   self._DBUS_SERVICE_PATH)
            self._authpolicyd = dbus.Interface(proxy, self._DBUS_INTERFACE_NAME)
        finally:
            os.setresuid(0, 0, 0)


    def __del__(self):
        """
        Destructor

        Turns debug logs off.

        """

        self.set_default_log_level(0)


    def join_ad_domain(self, machine_name, username, password):
        """
        Joins a machine (=device) to an Active Directory domain.

        @param machine_name: Name of the machine (=device) to be joined to the
                             Active Directory domain.
        @param username: User logon name (user@example.com) for the Active
                         Directory domain.
        @param password: Password corresponding to username.

        @return ErrorType from the D-Bus call.

        """

        with self.PasswordFd(password) as password_fd:
            return self._authpolicyd.JoinADDomain(
                    dbus.String(machine_name),
                    dbus.String(username),
                    dbus.types.UnixFd(password_fd))


    def authenticate_user(self, username, account_id, password):
        """
        Authenticates a user with an Active Directory domain.

        @param username: User logon name (user@example.com) for the Active
                         Directory domain.
        #param account_id: User account id (aka objectGUID). May be empty.
        @param password: Password corresponding to username.

        @return A tuple with the ErrorType and an ActiveDirectoryAccountInfo
                blob string returned by the D-Bus call.

        """

        with self.PasswordFd(password) as password_fd:
            return self._authpolicyd.AuthenticateUser(
                    dbus.String(username),
                    dbus.String(account_id),
                    dbus.types.UnixFd(password_fd))


    def refresh_user_policy(self, account_id_key):
        """
        Fetches user policy and sends it to Session Manager.

        @param account_id_key: User account ID (aka objectGUID) prefixed by "a-"

        @return ErrorType from the D-Bus call.

        """

        return self._authpolicyd.RefreshUserPolicy(dbus.String(account_id_key))


    def refresh_device_policy(self):
        """
        Fetches device policy and sends it to Session Manager.

        @return ErrorType from the D-Bus call.

        """

        return self._authpolicyd.RefreshDevicePolicy()


    def set_default_log_level(self, level):
        """
        Fetches device policy and sends it to Session Manager.

        @param level: Log level, 0=quiet, 1=taciturn, 2=chatty, 3=verbose.

        @return error_message: Error message, empty if no error occurred.

        """

        return self._authpolicyd.SetDefaultLogLevel(level)


    def print_log_tail(self):
        """
        Prints out authpolicyd log tail. Catches and prints out errors.

        """

        try:
            cmd = 'tail -n %s %s' % (self._LOG_LINE_LIMIT, self._LOG_FILE)
            log_tail = utils.run(cmd).stdout
            logging.info('Tail of %s:\n%s', self._LOG_FILE, log_tail)
        except error.CmdError as e:
            logging.error(
                    'Failed to print authpolicyd log tail: %s', e)


    def print_seccomp_failure_info(self):
        """
        Detects seccomp failures and prints out the failing syscall.

        """

        # Exit code 253 is minijail's marker for seccomp failures.
        cmd = 'grep -q "failed: exit code 253" %s' % self._LOG_FILE
        if utils.run(cmd, ignore_status=True).exit_status == 0:
            logging.error('Seccomp failure detected!')
            cmd = 'grep -oE "blocked syscall: \w+" %s | tail -1' % \
                    self._SYSLOG_FILE
            try:
                logging.error(utils.run(cmd).stdout)
                logging.error(
                        'This can happen if you changed a dependency of '
                        'authpolicyd. Consider whitelisting this syscall in '
                        'the appropriate -seccomp.policy file in authpolicyd.'
                        '\n')
            except error.CmdError as e:
                logging.error(
                        'Failed to determine reason for seccomp issue: %s',
                        e)


    def clear_log(self):
        """
        Clears the authpolicy daemon's log file.

        """

        try:
            utils.run('echo "" > %s' % self._LOG_FILE)
        except error.CmdError as e:
            logging.error('Failed to clear authpolicyd log file: %s', e)


    class PasswordFd(object):
        """
        Writes password into a file descriptor.

        Use in a 'with' statement to automatically close the returned file
        descriptor.

        @param password: Plaintext password string.

        @return A file descriptor (pipe) containing the password.

        """

        def __init__(self, password):
          self._password = password
          self._read_fd = None


        def __enter__(self):
          """Creates the password file descriptor."""
          self._read_fd, write_fd = os.pipe()
          os.write(write_fd, self._password)
          os.close(write_fd)
          return self._read_fd


        def __exit__(self, type, value, traceback):
          """Closes the password file descriptor again."""
          if self._read_fd:
            os.close(self._read_fd)

