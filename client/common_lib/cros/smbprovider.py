# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys

import dbus

from autotest_lib.client.cros import upstart

class SmbProvider(object):
    """
    Wrapper for D-Bus calls to SmbProvider Daemon

    The SmbProvider daemon handles calling the libsmbclient to communicate with
    an SMB server. This class is a wrapper to the D-Bus interface to the daemon.

    """

    _DBUS_SERVICE_NAME = "org.chromium.SmbProvider"
    _DBUS_SERVICE_PATH = "/org/chromium/SmbProvider"
    _DBUS_INTERFACE_NAME = "org.chromium.SmbProvider"

    # Default timeout in seconds for D-Bus calls.
    _DEFAULT_TIMEOUT = 120

    # Chronos user ID.
    _CHRONOS_UID = 1000

    def __init__(self, bus_loop, proto_binding_location):
        """
        Constructor.

        Creates and D-Bus connection to smbproviderd.

        @param bus_loop: Glib main loop object
        @param proto_binding_location: The location of generated python bindings
        for smbprovider protobufs.

        """

        sys.path.append(proto_binding_location)
        self._bus_loop = bus_loop
        self.restart()

    def restart(self):
        """
        Restarts smbproviderd and rebinds to D-Bus interface.

        """

        logging.info('restarting smbproviderd')
        upstart.restart_job('smbproviderd')

        try:
            # Get the interface as Chronos since only they are allowed to send
            # D-Bus messages to smbproviderd.
            os.setresuid(self._CHRONOS_UID, self._CHRONOS_UID, 0)

            bus = dbus.SystemBus(self._bus_loop)
            proxy = bus.get_object(self._DBUS_SERVICE_NAME,
                                   self._DBUS_SERVICE_PATH)
            self._smbproviderd = dbus.Interface(proxy,
                                                self._DBUS_INTERFACE_NAME)

        finally:
            os.setresuid(0, 0, 0)

    def stop(self):
        """
        Stops smbproviderd.

        """

        logging.info('stopping smbproviderd')

        try:
            upstart.stop_job('smbproviderd')

        finally:
            self._smbproviderd = None

    def mount(self, mount_path, workgroup, username, password):
        """
        Mounts a share.

        @param mount_path: Path of the share to mount.
        @param workgroup: Workgroup for the mount.
        @param username: Username for the mount.
        @param password: Password for the mount.

        @return A tuple with the ErrorType and the mount id returned the D-Bus
        call.

        """

        logging.info("Mounting: %s", mount_path)

        from directory_entry_pb2 import MountOptionsProto

        proto = MountOptionsProto()
        proto.path = mount_path
        proto.workgroup = workgroup
        proto.username = username

        with self.PasswordFd(password) as password_fd:
            return self._smbproviderd.Mount(
                    dbus.ByteArray(proto.SerializeToString()),
                    dbus.types.UnixFd(password_fd),
                    timeout=self._DEFAULT_TIMEOUT,
                    byte_arrays=True)

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

        def __exit__(self, mytype, value, traceback):
            """Closes the password file descriptor again."""

            if self._read_fd:
                os.close(self._read_fd)