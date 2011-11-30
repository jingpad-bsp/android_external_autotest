# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, platform, re, signal, tempfile, time, uuid
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

class TimeoutError(error.TestError):
    """Error raised when we time out when waiting on a condition."""
    pass


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


def nuke_process_by_name(name, with_prejudice=False):
    try:
        pid = int(utils.system_output('pgrep -o ^%s$' % name).split()[0])
    except Exception as e:
        logging.error(e)
        return
    if with_prejudice:
        utils.nuke_pid(pid, [signal.SIGKILL])
    else:
        utils.nuke_pid(pid)


def poll_for_condition(
    condition, exception=None, timeout=10, sleep_interval=0.1, desc=None):
    """Poll until a condition becomes true.

    Arguments:
      condition: function taking no args and returning bool
      exception: exception to throw if condition doesn't become true
      timeout: maximum number of seconds to wait
      sleep_interval: time to sleep between polls
      desc: description of default TimeoutError used if 'exception' is None

    Returns:
      The true value that caused the poll loop to terminate.

    Raises:
        'exception' arg if supplied; site_utils.TimeoutError otherwise
    """
    start_time = time.time()
    while True:
        value = condition()
        if value:
            return value
        if time.time() + sleep_interval - start_time > timeout:
            if exception:
                logging.error(exception)
                raise exception

            if desc:
                desc = 'Timed out waiting for condition: %s' % desc
            else:
                desc = 'Timed out waiting for unnamed condition'
            logging.error(desc)
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

def verify_mesg_set(mesg, regex, whitelist):
    """Verifies that the exact set of messages are present in a text.

    This function finds all strings in the text matching a certain regex, and
    then verifies that all expected strings are present in the set, and no
    unexpected strings are there.

    Arguments:
      mesg - the mutiline text to be scanned
      regex - regular expression to match
      whitelist - messages to find in the output, a list of strings
          (potentially regexes) to look for in the filtered output. All these
          strings must be there, and no other strings should be present in the
          filtered output.

    Returns:
      string of inconsistent findings (i.e. an empty string on success).
    """

    rv = []

    missing_strings = []
    present_strings = []
    for line in mesg.splitlines():
        if not re.search(r'%s' % regex, line):
            continue
        present_strings.append(line.split('] ', 1)[1])

    for string in whitelist:
        for present_string in list(present_strings):
            if re.search(r'^%s$' % string, present_string):
                present_strings.remove(present_string)
                break
        else:
            missing_strings.append(string)

    if present_strings:
        rv.append('unexpected strings:')
        rv.extend(present_strings)
    if missing_strings:
        rv.append('missing strings:')
        rv.extend(missing_strings)

    return '\n'.join(rv)


def target_is_x86_pie():
    """Returns whether the toolchain produces an x86 PIE (position independent
    executable) by default.

    Arguments:
      None

    Returns:
      True if the target toolchain produces an x86 PIE by default.
      False otherwise.
    """


    command = "echo \"int main(){return 0;}\" | ${CC} -o /tmp/a.out -xc -"
    command += "&& file /tmp/a.out"
    result = utils.system_output(command, retain_output=True,
                                 ignore_status=True)
    if re.search("80\d86", result) and re.search("shared object", result):
        return True
    else:
        return False

def mounts():
    ret = []
    for line in file('/proc/mounts'):
        m = re.match(r'(?P<src>\S+) (?P<dest>\S+) (?P<type>\S+) (?P<opts>\S+).*', line)
        if m:
            ret.append(m.groupdict())
    return ret

def is_mountpoint(path):
    return path in [ m['dest'] for m in mounts() ]

def require_mountpoint(path):
    """
    Raises an exception if path is not a mountpoint.
    """
    if not is_mountpoint(path):
        raise error.TestFail('Path not mounted: "%s"' % path)

def random_username():
    return str(uuid.uuid4()) + '@example.com'
