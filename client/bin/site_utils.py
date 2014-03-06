#pylint: disable-msg=C0111

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


def get_oldest_pid_by_name(name):
    """
    Return the oldest pid of a process whose name perfectly matches |name|.

    name is an egrep expression, which will be matched against the entire name
    of processes on the system.  For example:

      get_oldest_pid_by_name('chrome')

    on a system running
      8600 ?        00:00:04 chrome
      8601 ?        00:00:00 chrome
      8602 ?        00:00:00 chrome-sandbox

    would return 8600, as that's the oldest process that matches.
    chrome-sandbox would not be matched.

    Arguments:
      name: egrep expression to match.  Will be anchored at the beginning and
            end of the match string.

    Returns:
      pid as an integer, or None if one cannot be found.

    Raises:
      ValueError if pgrep returns something odd.
    """
    str_pid = utils.system_output(
        'pgrep -o ^%s$' % name, ignore_status=True).rstrip()
    if str_pid:
        return int(str_pid)


def get_oldest_by_name(name):
    """Return pid and command line of oldest process whose name matches |name|.

    @param name: egrep expression to match desired process name.
    @return: A tuple of (pid, command_line) of the oldest process whose name
             matches |name|.

    """
    pid = get_oldest_pid_by_name(name)
    if pid:
        command_line = utils.system_output('ps -p %i -o command=' % pid,
                                           ignore_status=True).rstrip()
        return (pid, command_line)


def get_chrome_remote_debugging_port():
    """Returns remote debugging port for Chrome.

    Parse chrome process's command line argument to get the remote debugging
    port.
    """
    pid, command = get_oldest_by_name('chrome')
    matches = re.search('--remote-debugging-port=([0-9]+)', command)
    if matches:
        return int(matches.group(1))


def get_process_list(name, command_line=None):
    """
    Return the list of pid for matching process |name command_line|.

    on a system running
      31475 ?    0:06 /opt/google/chrome/chrome --allow-webui-compositing -
      31478 ?    0:00 /opt/google/chrome/chrome-sandbox /opt/google/chrome/
      31485 ?    0:00 /opt/google/chrome/chrome --type=zygote --log-level=1
      31532 ?    1:05 /opt/google/chrome/chrome --type=renderer

    get_process_list('chrome')
    would return ['31475', '31485', '31532']

    get_process_list('chrome', '--type=renderer')
    would return ['31532']

    Arguments:
      name: process name to search for. If command_line is provided, name is
            matched against full command line. If command_line is not provided,
            name is only matched against the process name.
      command line: when command line is passed, the full process command line
                    is used for matching.

    Returns:
      list of PIDs of the matching processes.

    """
    # TODO(rohitbm) crbug.com/268861
    flag = '-x' if not command_line else '-f'
    name = '\'%s.*%s\'' % (name, command_line) if command_line else name
    str_pid = utils.system_output(
            'pgrep %s %s' % (flag, name), ignore_status=True).rstrip()
    return str_pid


def nuke_process_by_name(name, with_prejudice=False):
    try:
        pid = get_oldest_pid_by_name(name)
    except Exception as e:
        logging.error(e)
        return
    if pid is None:
        raise error.AutoservPidAlreadyDeadError(
            'No process matching %s.' % name)
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
        logging.info('Saving VM state "%s"', checkpoint)
        serial = open('/dev/ttyUSB0', 'w')
        serial.write("savevm %s\r\n" % checkpoint)
        logging.info('Done saving VM state "%s"', checkpoint)


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


def target_is_pie():
    """Returns whether the toolchain produces a PIE (position independent
    executable) by default.

    Arguments:
      None

    Returns:
      True if the target toolchain produces a PIE by default.
      False otherwise.
    """


    command = 'echo | ${CC} -E -dD -P - | grep -i pie'
    result = utils.system_output(command, retain_output=True,
                                 ignore_status=True)
    if re.search('#define __PIE__', result):
        return True
    else:
        return False

def target_is_x86():
    """Returns whether the toolchain produces an x86 object

    Arguments:
      None

    Returns:
      True if the target toolchain produces an x86 object
      False otherwise.
    """


    command = 'echo | ${CC} -E -dD -P - | grep -i 86'
    result = utils.system_output(command, retain_output=True,
                                 ignore_status=True)
    if re.search('__i386__', result) or re.search('__x86_64__', result):
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


def parse_cmd_output(command, run_method=utils.run):
    """Runs a command on a host object to retrieve host attributes.

    The command should output to stdout in the format of:
    <key> = <value> # <optional_comment>


    @param command: Command to execute on the host.
    @param run_method: Function to use to execute the command. Defaults to
                       utils.run so that the command will be executed locally.
                       Can be replace with a host.run call so that it will
                       execute on a DUT or external machine. Method must accept
                       a command argument, stdout_tee and stderr_tee args and
                       return a result object with a string attribute stdout
                       which will be parsed.

    @returns a dictionary mapping host attributes to their values.
    """
    result = {}
    # Suppresses stdout so that the files are not printed to the logs.
    cmd_result = run_method(command, stdout_tee=None, stderr_tee=None)
    for line in cmd_result.stdout.splitlines():
        # Lines are of the format "<key>     = <value>      # <comment>"
        key_value = re.match('^\s*(?P<key>[^ ]+)\s*=\s*(?P<value>[^ ]+)'
                             '(?:\s*#.*)?$', line)
        if key_value:
            result[key_value.group('key')] = key_value.group('value')
    return result


def set_from_keyval_output(out, delimiter=' '):
    """Parse delimiter-separated key-val output into a set of tuples.

    Output is expected to be multiline text output from a command.
    Stuffs the key-vals into tuples in a set to be later compared.

    e.g.  deactivated 0
          disableForceClear 0
          ==>  set(('deactivated', '0'), ('disableForceClear', '0'))

    @param out: multiple lines of space-separated key-val pairs.
    @param delimiter: character that separates key from val. Usually a
                      space but may be '=' or something else.
    @return set of key-val tuples.
    """
    results = set()
    kv_match_re = re.compile('([^ ]+)%s(.*)' % delimiter)
    for linecr in out.splitlines():
        match = kv_match_re.match(linecr.strip())
        if match:
            results.add((match.group(1), match.group(2)))
    return results


def get_cpu_usage():
    """Returns machine's CPU usage.

    This function uses /proc/stat to identify CPU usage.
    Returns:
        A dictionary with 'user', 'nice', 'system' and 'idle' values.
        Sample dictionary:
        {
            'user': 254544,
            'nice': 9,
            'system': 254768,
            'idle': 2859878,
        }
    """
    proc_stat = open('/proc/stat')
    cpu_usage_str = proc_stat.readline().split()
    proc_stat.close()
    return {
        'user': int(cpu_usage_str[1]),
        'nice': int(cpu_usage_str[2]),
        'system': int(cpu_usage_str[3]),
        'idle': int(cpu_usage_str[4])
    }


def compute_active_cpu_time(cpu_usage_start, cpu_usage_end):
    """Computes the fraction of CPU time spent non-idling.

    This function should be invoked using before/after values from calls to
    get_cpu_usage().
    """
    time_active_end = (cpu_usage_end['user'] + cpu_usage_end['nice'] +
                                                  cpu_usage_end['system'])
    time_active_start = (cpu_usage_start['user'] + cpu_usage_start['nice'] +
                                                      cpu_usage_start['system'])
    total_time_end = (cpu_usage_end['user'] + cpu_usage_end['nice'] +
                      cpu_usage_end['system'] + cpu_usage_end['idle'])
    total_time_start = (cpu_usage_start['user'] + cpu_usage_start['nice'] +
                        cpu_usage_start['system'] + cpu_usage_start['idle'])
    return ((float(time_active_end) - time_active_start) /
                    (total_time_end - total_time_start))


def is_pgo_mode():
    return 'USE_PGO' in os.environ


def wait_for_idle_cpu(timeout, utilization):
    """Waits for the CPU to become idle (< utilization).

    Args:
        timeout: The longest time in seconds to wait before throwing an error.
        utilization: The CPU usage below which the system should be considered
                idle (between 0 and 1.0 independent of cores/hyperthreads).
    """
    time_passed = 0.0
    fraction_active_time = 1.0
    sleep_time = 1
    logging.info('Starting to wait up to %.1fs for idle CPU...', timeout)
    while fraction_active_time >= utilization:
        cpu_usage_start = get_cpu_usage()
        # Split timeout interval into not too many chunks to limit log spew.
        # Start at 1 second, increase exponentially
        time.sleep(sleep_time)
        time_passed += sleep_time
        sleep_time = min(16.0, 2.0 * sleep_time)
        cpu_usage_end = get_cpu_usage()
        fraction_active_time = \
                compute_active_cpu_time(cpu_usage_start, cpu_usage_end)
        logging.info('After waiting %.1fs CPU utilization is %f.',
                     time_passed, fraction_active_time)
        if time_passed > timeout:
            logging.warning('CPU did not become idle.')
            log_process_activity()
            # crosbug.com/37389
            if is_pgo_mode():
                logging.info('Still continuing because we are in PGO mode.')
                return True

            return False
    logging.info('Wait for idle CPU took %fs (utilization = %f).',
                              time_passed, fraction_active_time)
    return True


def log_process_activity():
    """Logs the output of top.

    Useful to debug performance tests and to find runaway processes.
    """
    logging.info('Logging current process activity using top.')
    cmd = 'top -b -n1 -c'
    output = utils.run(cmd)
    logging.info(output)


def wait_for_cool_cpu():
    # TODO(ihf): Implement this.
    return True


def wait_for_cool_idle_perf_machine():
    # Wait for 60 seconds for the CPU usage to fall under 10%.
    if not wait_for_idle_cpu(60, 0.1):
        return False
    return wait_for_cool_cpu()

