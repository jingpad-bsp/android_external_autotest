# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to provide interface to ChromeOS services."""

import datetime
import os
import re
import struct
import subprocess

class ChromeOSInterfaceError(Exception):
    """ChromeOS interface specific exception."""
    pass

class Crossystem(object):
    """A wrapper for the crossystem utility."""

    # Code dedicated for user triggering recovery mode through crossystem.
    USER_RECOVERY_REQUEST_CODE = '193'

    def init(self, cros_if):
        """Init the instance. If running on Mario - adjust the map."""
        self.cros_if = cros_if

    def __getattr__(self, name):
        """
        Retrieve a crosssystem attribute.

        Attempt to access crossystemobject.name will invoke `crossystem name'
        and return the stdout as the value.
        """
        return self.cros_if.run_shell_command_get_output(
            'crossystem %s' % name)[0]

    def __setattr__(self, name, value):
        if name in ('cros_if',):
            self.__dict__[name] = value
        else:
            self.cros_if.run_shell_command('crossystem "%s=%s"' % (name, value))

    def request_recovery(self):
        """Request recovery mode next time the target reboots."""

        self.__setattr__('recovery_request', self.USER_RECOVERY_REQUEST_CODE)


class ChromeOSInterface(object):
    """An object to encapsulate OS services functions."""

    def __init__(self, silent):
        """Object construction time initialization.

        The only parameter is the Boolean 'silent', when True the instance
        does not duplicate log messages on the console.
        """

        self.silent = silent
        self.state_dir = None
        self.log_file = None
        self.cs = Crossystem()

    def init(self, state_dir=None, log_file=None):
        """Initialize the ChromeOS interface object.
        Args:
          state_dir - a string, the name of the directory (as defined by the
                      caller). The contents of this directory persist over
                      system restarts and power cycles.
          log_file - a string, the name of the log file kept in the state
                     directory.

        Default argument values support unit testing.
        """

        self.cs.init(self)
        self.state_dir = state_dir

        if self.state_dir:
            if not os.path.exists(self.state_dir):
                try:
                    os.mkdir(self.state_dir)
                except OSError, err:
                    raise ChromeOSInterfaceError(err)
            if log_file:
                if log_file[0] == '/':
                    self.log_file = log_file
                else:
                    self.log_file = os.path.join(state_dir, log_file)

    def target_hosted(self):
        """Return True if running on a ChromeOS target."""
        signature = open('/etc/lsb-release', 'r').readlines()[0]
        return re.search(r'chrom(ium|e)os', signature, re.IGNORECASE) != None

    def state_dir_file(self, file_name):
        """Get a full path of a file in the state directory."""
        return os.path.join(self.state_dir, file_name)

    def log(self, text):
        """Write text to the log file and print it on the screen, if enabled.

        The entire log (maintained across reboots) can be found in
        self.log_file.
        """

        # Don't print on the screen unless enabled.
        if not self.silent:
            print text

        if not self.log_file or not os.path.exists(self.state_dir):
            # Called before environment was initialized, ignore.
            return

        timestamp = datetime.datetime.strftime(
            datetime.datetime.now(), '%I:%M:%S %p:')

        with open(self.log_file, 'a') as log_f:
            log_f.write('%s %s\n' % (timestamp, text))
            log_f.flush()
            os.fdatasync(log_f)

    def run_shell_command(self, cmd):
        """Run a shell command.

        In case of the command returning an error print its stdout and stderr
        outputs on the console and dump them into the log. Otherwise suppress all
        output.

        In case of command error raise an OSInterfaceError exception.

        Return the subprocess.Popen() instance to provide access to console
        output in case command succeeded.
        """

        self.log('Executing %s' % cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        process.wait()
        if process.returncode:
            err = ['Failed running: %s' % cmd]
            err.append('stdout:')
            err.append(process.stdout.read())
            err.append('stderr:')
            err.append(process.stderr.read())
            text = '\n'.join(err)
            print text
            self.log(text)
            raise ChromeOSInterfaceError('command %s failed' % cmd)
        return process

    def is_removable_device(self, device):
        """Check if a certain storage device is removable.

        device - a string, file name of a storage device or a device partition
                 (as in /dev/sda[0-9] or /dev/mmcblk0p[0-9]).

        Returns True if the device is removable, False if not.
        """

        if not self.target_hosted():
            return False

        # Drop trailing digit(s) and letter(s) (if any)
        base_dev = self.strip_part(device.split('/')[2])
        removable = int(open('/sys/block/%s/removable' % base_dev, 'r').read())

        return removable == 1

    def get_internal_disk(self, device):
        """Get the internal disk by given the current disk.

        If device is removable device, internal disk is decided by which kind
        of divice (arm or x86). Otherwise, return device itself.

        device - a string, file name of a storage device or a device partition
                 (as in /dev/sda[0-9] or /dev/mmcblk0p[0-9]).

        Return internal kernel disk.
        """
        if self.is_removable_device(device):
            if os.path.exists('/dev/mmcblk0'):
                return '/dev/mmcblk0'
            else:
                return '/dev/sda'
        else:
            return self.strip_part(device)

    def get_root_part(self):
        """Return a string, the name of root device with partition number"""
        return self.run_shell_command_get_output('rootdev -s')[0]

    def get_root_dev(self):
        """Return a string, the name of root device without partition number"""
        return self.strip_part(self.get_root_part())

    def join_part(self, dev, part):
        """Return a concatenated string of device and partition number"""
        if 'mmcblk' in dev:
            return dev + 'p' + part
        else:
            return dev + part

    def strip_part(self, dev_with_part):
        """Return a stripped string without partition number"""
        dev_name_stripper = re.compile('p?[0-9]+$')
        return dev_name_stripper.sub('', dev_with_part)

    def run_shell_command_get_output(self, cmd):
        """Run shell command and return its console output to the caller.

        The output is returned as a list of strings stripped of the newline
        characters."""

        process = self.run_shell_command(cmd)
        return [x.rstrip() for x in process.stdout.readlines()]

    def retrieve_body_version(self, blob):
        """Given a blob, retrieve body version.

        Currently works for both, firmware and kernel blobs. Returns '-1' in
        case the version can not be retrieved reliably.
        """
        header_format = '<8s8sQ'
        preamble_format = '<40sQ'
        magic, _, kb_size = struct.unpack_from(header_format, blob)

        if magic != 'CHROMEOS':
            return -1  # This could be a corrupted version case.

        _, version = struct.unpack_from(preamble_format, blob, kb_size)
        return version

    def retrieve_datakey_version(self, blob):
        """Given a blob, retrieve firmware data key version.

        Currently works for both, firmware and kernel blobs. Returns '-1' in
        case the version can not be retrieved reliably.
        """
        header_format = '<8s96sQ'
        magic, _, version = struct.unpack_from(header_format, blob)
        if magic != 'CHROMEOS':
            return -1 # This could be a corrupted version case.
        return version

    def retrieve_kernel_subkey_version(self, blob):
        """Given a blob, retrieve kernel subkey version.

        It is in firmware vblock's preamble.
        """

        header_format = '<8s8sQ'
        preamble_format = '<72sQ'
        magic, _, kb_size = struct.unpack_from(header_format, blob)

        if magic != 'CHROMEOS':
            return -1

        _, version = struct.unpack_from(preamble_format, blob, kb_size)
        return version

    def retrieve_preamble_flags(self, blob):
        """Given a blob, retrieve preamble flags if available.

        It only works for firmware. If the version of preamble header is less
        than 2.1, no preamble flags supported, just returns 0.
        """
        header_format = '<8s8sQ'
        preamble_format = '<32sII64sI'
        magic, _, kb_size = struct.unpack_from(header_format, blob)

        if magic != 'CHROMEOS':
            return -1  # This could be a corrupted version case.

        _, ver, subver, _, flags = struct.unpack_from(preamble_format, blob,
                                                      kb_size)

        if ver > 2 or (ver == 2 and subver >= 1):
            return flags
        else:
            return 0  # Returns 0 if preamble flags not available.

    def read_partition(self, partition, size):
        """Read the requested partition, up to size bytes."""
        tmp_file = self.state_dir_file('part.tmp')
        self.run_shell_command('dd if=%s of=%s bs=1 count=%d' % (
                partition, tmp_file, size))
        fileh = open(tmp_file, 'r')
        data = fileh.read()
        fileh.close()
        os.remove(tmp_file)
        return data
