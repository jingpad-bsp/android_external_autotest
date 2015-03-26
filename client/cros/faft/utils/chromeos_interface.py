# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to provide interface to ChromeOS services."""

import datetime
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time

class ChromeOSInterfaceError(Exception):
    """ChromeOS interface specific exception."""
    pass

class Crossystem(object):
    """A wrapper for the crossystem utility."""

    # Code dedicated for user triggering recovery mode through crossystem.
    USER_RECOVERY_REQUEST_CODE = '193'

    """
    The first three legacy boot vector digits are the boot vector base (the
    entire vector consists of 5 digits). They used to be reported by the BIOS
    through ACPI, but that scheme has been superseded by the 'crossystem'
    interface.

    The digits of the boot vector base have the following significance

    - first digit -
    1 - normal boot
    2 - developer mode boot
    3 - recovery initialed by pressing the recovery button
    4 - recovery from developer mode warning screen
    5 - recovery caused by both firmware images being invalid
    6 - recovery caused by both kernel images being invalid
    8 - recovery initiated by user

    - second digit -
    0 - recovery firmware
    1 - rewritable firmware A
    2 - rewritable firmware B

    - third digit -
    0 - Read only (recovery) EC firmware
    1 - rewritable EC firmware


    Below is a list of dictionaries to map current system state as reported by
    'crossystem' into the 'legacy' boot vector digits.

    The three elements of the list represent the three digits of the boot
    vector. Each list element is a dictionary where the key is the legacy boot
    vector value in the appropriate position, and the value is in turn a
    dictionary of name-value pairs.

    If all name-value pairs of a dictionary element match those reported by
    crossystem, the legacy representation number is considered the appropriate
    vector digit.

    Note that on some platforms (namely, Mario) same parameters returned by
    crossystem are set to a wrong value. The class init() routine adjust the
    list to support those platforms.
    """

    VECTOR_MAPS = [
        { # first vector position
            '1': {
                'devsw_boot': '0',
                'mainfw_type': 'normal',
                'recoverysw_boot': '0',
                },
            '2': {
                'devsw_boot': '1',
                'mainfw_type': 'developer',
                'recoverysw_boot': '0',
                },
            '3': {
                'devsw_boot': '0',
                'mainfw_type': 'recovery',
                'recovery_reason' : '2',
                'recoverysw_boot': '1',
                },
            '4': {
                'devsw_boot': '1',
                'mainfw_type': 'recovery',
                'recovery_reason' : '65',
                'recoverysw_boot': '0',
                },
            '5': {
                'devsw_boot': '0',
                'mainfw_type': 'recovery',
                'recovery_reason' : ('3', '23', '27'),
                'recoverysw_boot': '0',
                },
            '6': {
                'devsw_boot': '0',
                'mainfw_type': 'recovery',
                'recovery_reason' : '66',
                'recoverysw_boot': '0',
                },
            '8': {
                'devsw_boot': '0',
                'mainfw_type': 'recovery',
                'recovery_reason' : USER_RECOVERY_REQUEST_CODE,
                'recoverysw_boot': '0',
                },
            },
        { # second vector position
            '0': {'mainfw_type': 'recovery',},
            '1': {'mainfw_act': 'A',},
            '2': {'mainfw_act': 'B',},
            },
        { # third vector position
            '0': {'ecfw_act': 'RO',},
            '1': {'ecfw_act': 'RW',},
            # Skip the ecfw_act check when the value is neither 'RO' nor 'RW'.
            # It happens on non-Chrome-EC devices.
            '*': {},
            },
        ]

    def init(self, cros_if):
        """Init the instance. If running on Mario - adjust the map."""

        self.cros_if = cros_if

        # Hack Alert!!! Adjust vector map to work on Mario
        fwid = self.__getattr__('fwid').lower()
        if not 'mario' in fwid:
            return
        # Mario firmware is broken and always reports recovery switch as set
        # at boot time when booting up in recovery mode. This is why we
        # exclude recoverysw_boot from the map when running on mario.
        for state in self.VECTOR_MAPS[0].itervalues():
            if state['mainfw_type'] != 'recovery':
                continue
            if 'recoverysw_boot' in state:
                del(state['recoverysw_boot'])
            if state['recovery_reason'] == self.USER_RECOVERY_REQUEST_CODE:
                # This is the only recovery reason Mario knows about
                state['recovery_reason'] = '1'

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

    def get_boot_vector_base(self):
        """Convert system state into a legacy boot vector base.

        The function looks up the VECTOR_MAPS list above to find the digits
        matching the current crossystem output, and returns a list of three
        digits in symbolic representation, which become the base of the 5
        digit boot state vector.

        Should it be impossible to interpret the state, the function returns
        a partially built list, which is an indication of a problem for the
        caller (list shorter than 3 elements).
        """

        boot_vector = []

        for vector_map in self.VECTOR_MAPS:
            for (digit, values) in vector_map.iteritems():
                for (name, value) in values.iteritems():
                    try:
                        # Get the actual attribute value from crossystem.
                        attr_value = self.__getattr__(name)
                    except ChromeOSInterfaceError:
                        # Skip the error in case of missing field in crossystem.
                        break
                    if isinstance(value, str):
                        if attr_value != value:
                            break
                    else:
                        # 'value' is a tuple of possible actual values.
                        if attr_value not in value:
                            break
                else:
                    boot_vector.append(digit)
                    break

        return boot_vector

    def dump(self):
        """Dump all crossystem values as multiline text."""

        return '\n'.join(self.cros_if.run_shell_command_get_output(
            'crossystem'))


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

    def init_environment(self):
        """Initialize Chrome OS interface environment.

        If state dir was not set up by the constructor, create a temp
        directory, otherwise create the directory defined during construction
        of this object.

        Return the state directory name.
        """

        if not self.state_dir:
            self.state_dir = tempfile.mkdtemp(suffix='_saft')
        else:
            # Wipe out state directory, to start the state machine clean.
            shutil.rmtree(self.state_dir)
            # And recreate it
            self.init(self.state_dir, self.log_file)

        return self.state_dir

    def shut_down(self, new_log='/var/saft_log.txt'):
        """Destroy temporary environment so that the test can be restarted."""
        if os.path.exists(self.log_file):
            shutil.copyfile(self.log_file, new_log)
        shutil.rmtree(self.state_dir)

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


    def exec_exists(self, program):
        """Check if the passed in string is a valid executable found in PATH."""

        for path in os.environ['PATH'].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if (os.path.isfile(exe_file) or os.path.islink(exe_file)
                ) and os.access(exe_file, os.X_OK):
                return True
        return False

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

    def boot_state_vector(self):
        """Read and return to caller a string describing the system state.

        The string has a form of x0:x1:x2:<removable>:<partition_number>,
        where the field meanings of X# are described in the
        Crossystem.get_boot_vector_base() docstring above.

        <removable> is set to 1 or 0 depending if the root device is removable
        or not, and <partition number> is the last element of the root device
        name, designating the partition where the root fs is mounted.

        This vector fully describes the way the system came up.
        """

        state = self.cs.get_boot_vector_base()

        if len(state) != 3:
            raise ChromeOSInterfaceError(self.cs.dump())

        root_part = self.get_root_part()
        state.append('%d' % int(self.is_removable_device(root_part)))
        state.append('%s' % root_part[-1])
        state_str = ':'.join(state)
        return state_str

    def cmp_boot_vector(self, vector1, vector2):
        """Compare if the two boot vectors are the same

        Note: a wildcard (*) will match any value.
        """
        list1 = vector1.split(':')
        list2 = vector2.split(':')
        if len(list1) != len(list2):
            raise ChromeOSInterfaceError(
                    'Boot vectors (%s %s) should be of the same length'
                    % (vecotr1, vector2))
        for i in range(len(list1)):
            if list1[i] != list2[i] and list1[i] != '*' and list2[i] != '*':
                return False
        return True

    def get_writeable_mount_point(self, dev, tmp_dir):
        """Get mountpoint of the passed in device mounted in read/write mode.

      If the device is already mounted and is writeable - return its mount
      point. If the device is mounted but read-only - remount it read/write
      and return its mount point. If the device is not mounted - mount it read
      write on the passsed in path and return this path.
      """

      # The device root file system is mounted on is represented as /dev/root
      # otherwise.
        options_filter = re.compile('.*\((.+)\).*')
        root_part = self.get_root_part()
        if dev == root_part:
            dev = '/dev/root'

        for line in self.run_shell_command_get_output('mount'):
            if not line.startswith('%s ' % dev):
                continue
            mount_options = options_filter.match(line).groups(0)[0]
        # found mounted
            if 'ro' in mount_options.split(','):
          # mounted read only
                self.run_shell_command('mount -o remount,rw %s' % dev)
            return line.split()[2]  # Mountpoint is the third element.
      # Not found, needs to be mounted
        self.run_shell_command('mount %s %s' % (dev, tmp_dir))
        return tmp_dir

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
