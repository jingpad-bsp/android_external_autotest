# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, platform, re, tempfile, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class TimeoutError(error.TestError):
    """Error raised when we time out when waiting on a condition."""


class Crossystem(object):
    """A wrapper for the crossystem utility."""

    def __init__(self, client):
        self.cros_system_data = {}
        self._client = client

    def init(self):
        self.cros_system_data = {}
        (_, fname) = tempfile.mkstemp()
        f = open(fname, 'w')
        self._client.run('crossystem', stdout_tee=f)
        f.close()
        text = utils.read_file(fname)
        for line in text.splitlines():
            assignment_string = line.split('#')[0]
            if not assignment_string.count('='):
                continue
            (name, value) = assignment_string.split('=', 1)
            self.cros_system_data[name.strip()] = value.strip()
        os.remove(fname)

    def __getattr__(self, name):
        """
        Retrieve a crosssystem attribute.

        The call crossystemobject.name() will return the crossystem reported
        string.
        """
        return lambda : self.cros_system_data[name]


def poll_for_condition(
    condition, exception=None, timeout=10, sleep_interval=0.1, desc=None):
    """Poll until a condition becomes true.

    condition: function taking no args and returning bool
    exception: exception to throw if condition doesn't become true
    timeout: maximum number of seconds to wait
    sleep_interval: time to sleep between polls
    desc: description of default TimeoutError used if 'exception' is None

    Raises:
        'exception' arg if supplied; site_utils.TimeoutError otherwise
    """
    start_time = time.time()
    while True:
        if condition():
            return
        if time.time() + sleep_interval - start_time > timeout:
            if exception:
                raise exception

            if desc:
                desc = 'Timed out waiting for condition: %s' % desc
            else:
                desc = 'Timed out waiting for unnamed condition'
            raise TimeoutError, desc

        time.sleep(sleep_interval)


def save_vm_state(checkpoint):
    """Saves the current state of the virtual machine.

    This function is a NOOP if the test is not running under a virtual machine
    with the USB serial port redirected.

    Arguments:
      checkpoint - Name used to identify this state

    Returns:
      None
    """
    # The QEMU monitor has been redirected to the guest serial port located at
    # /dev/ttyUSB0. To save the state of the VM, we just send the 'savevm'
    # command to the serial port.
    proc = platform.processor()
    if 'QEMU' in proc and os.path.exists('/dev/ttyUSB0'):
        logging.info('Saving VM state "%s"' % checkpoint)
        serial = open('/dev/ttyUSB0', 'w')
        serial.write("savevm %s\r\n" % checkpoint)
        logging.info('Done saving VM state "%s"' % checkpoint)


def check_raw_dmesg(dmesg, message_level, whitelist):
    """Checks dmesg for unexpected warnings.

    This function parses dmesg for message with message_level <= message_level
    which do not appear in the whitelist.

    Arguments:
      dmesg - string containing raw dmesg buffer
      message_level - minimum message priority to check
      whitelist - messages to ignore

    Returns:
      List of unexpected warnings
    """
    whitelist_re = re.compile(r'(%s)' % '|'.join(whitelist))
    unexpected = []
    for line in dmesg.splitlines():
        if int(line[1]) <= message_level:
            stripped_line = line.split('] ', 1)[1]
            if whitelist_re.search(stripped_line):
                continue
            unexpected.append(stripped_line)
    return unexpected
