#!/usr/bin/env python

import collections
import multiprocessing.pool
import os
import re
import subprocess
import sys
import tempfile
import urllib2

import common
from autotest_lib.server import frontend
from autotest_lib.server import utils


SERVERS = ['cautotest', 'cautotest-cq']
RESULT_URL_FMT = 'http://%s/tko/retrieve_logs.cgi?job=/results'
LOG_PATH_FMT = 'hosts/%s/%d-repair'
AUTOSERV_DEBUG_LOG = 'debug/autoserv.DEBUG'
GS_URI =  'gs://chromeos-autotest-results'

REPAIR_FAILURE_PATTERN = re.compile('.*Failed to repair .*: (.*)')
REPAIR_ACTION_PATTERN = re.compile('.*Attempting (.*)')
NEW_LINE_PATTERN = re.compile('^\d\d/\d\d\s\d\d:\d\d:\d\d')
COMMAND_PATTERN = re.compile('[^"]*("[^"]*").*')

def ssh_command(host, cmd):
    return ['ssh', '-o PasswordAuthentication=no', '-o ConnectTimeout=1',
            '-o ConnectionAttempts=1', '-o StrictHostKeyChecking=no',
            '-q', 'root@'+host, '--', cmd]


class Result(object):
    def __init__(self, host, ping, ssh, servod, logs):
        self.host = host
        self.ping = ping
        self.ssh = ssh
        self.servod = servod
        self.logs = logs


class FailureReason(object):
    """Object used to store the detail of an attempt to repair.
    """
    def __init__(self, action, error, hostname):
        """Initialize the detail of an attempt to repair.

        @param action: Action taken to repair the DUT.
        @param error: Error message.
        @param hostname: Hostname of the repair failed DUT.
        """
        self.action = action
        self.error = error
        self.hostname = hostname
        self.key = self.get_key()


    def get_key(self):
        """Get a reason string that does not contain unnecessary information.

        @param reason: A string that explains repair failure.
        @param host: An attribute dictionary of host that failed to be repaired.
        @return: A simplified string that does not contain unnecessary
                 information, e.g., hostname etc.
        """
        # Merge error into a single line.
        error = self.error.replace('\n', ' ')
        # Remove repeated empty spaces.
        error = re.sub('\s\s+' , ' ', error)

        if '/usr/bin/ssh -a -x -o ControlPath=' in error:
            # Extract the command, and rebuild reason string.
            error = ('Failed to run command: %s' %
                     extract_match_text(error, COMMAND_PATTERN))

        reason = 'Action: %s. Error: %s' % (self.action, error)

        # Remove hostname from reason string.
        reason = reason.replace(self.hostname, '')

        # Trim reason string as some might be really long.
        reason = reason[:136]

        return reason


class Failure(object):
    """Object used to store the details of why a host is failed to be repaired.
    """
    def __init__(self, server, host, repair_job_id):
        """Initialize details of failure

        @param server: Name of Autotest instance.
        @param host: CrosHost object of the DUT.
        @param repair_job_id is the job ID of last repair job.
        """
        self.host = host
        self.repair_job_id = repair_job_id
        log_path = LOG_PATH_FMT % (host['hostname'], repair_job_id)
        self.log_url = '%s/%s' % (RESULT_URL_FMT % server, log_path)

        self.reasons = self.get_repair_fail_reasons()


    @classmethod
    def get_debug_log(self, autoserv_log_url, autoserv_log_path):
        """Get a list of strings or a stream for autoserv.DEBUG log file.

        @param autoserv_log_url: Url to the repair job's autoserv.DEBUG log.
        @param autoserv_log_path: Path to autoserv.DEBUG log, e.g.,
                            hosts/hostname/job_id-repair/debug/autoserv.DEBUG.
        @return: A list of string if debug log was moved to GS already, or a
                 stream of the autoserv.DEBUG file.
        """
        url = urllib2.urlopen(autoserv_log_url).geturl()
        if not 'accounts.google.com' in url:
            return urllib2.urlopen(url)
        else:
            # The file was moved to Google storage already, download it to /tmp
            debug_log_link = '%s/%s' % (GS_URI, autoserv_log_path)
            cmd = 'gsutil cat %s' % debug_log_link
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode == 0:
                return stdout.split(os.linesep)
            else:
                print 'Failed to read %s: %s' % (debug_log_link, stderr)


    @classmethod
    def is_log_entry(self, line):
        """Check if the given line is a log entry started with a timestamp.

        @param line: A single line in the log file.
        @return: True if the line is a new log entry that starts with a
                 timestamp.
        """
        return NEW_LINE_PATTERN.match(line) != None


    @classmethod
    def get_action(self, line):
        """Parse the action used to repair DUT.

        @param line: A single line in the log file.
        @return: Action used to repair DUT, None if the line does not have such
                 information.
        """
        action = extract_match_text(line, REPAIR_ACTION_PATTERN)
        # Trim `to `, some repair attempt (RPM) does not use that word.
        if action and action.startswith('to '):
            action = action[3:]
        # Ignore the line `Attempting full repair`
        if action == 'full repair':
            action = None
        return action


    def get_repair_fail_reasons(self):
        """Get a list of reasons for repair failure.

        Read through autoserv.DEBUG log to find each attempt to repair the DUT
        and the reason it failed. The sequence in the log looks like:
        Attempting full repair
        Attempting to repair servo host chromeos2-row5-rack1-host4-servo.
        Failed to repair servo: Host did not return from reboot
        Attempting recover servo enabled device by powering it off and on
        Failed to repair device: DUT did not boot after long_press.
        Attempting recovery servo enabled device with servo_repair_reinstall
        Failed to repair device: Download image to usb failed.
        Attempting repair via RPM powercycle.
        Failed to repair device: Powercycled host 6 times; device did not...

        @param autoserv_log_url: Url to the repair job's autoserv.DEBUG log.
        @param autoserv_log_path: Path to autoserv.DEBUG log, e.g.,
                            hosts/hostname/job_id-repair/debug/autoserv.DEBUG.
        @param hostname: Hostname of the repair failed DUT.
        @return: A list of reason strings.
        """
        hostname = self.host['hostname']
        log_path = LOG_PATH_FMT % (hostname, self.repair_job_id)
        autoserv_log_path = '%s/%s' % (log_path, AUTOSERV_DEBUG_LOG)
        autoserv_log_url = '%s/%s' % (self.log_url, AUTOSERV_DEBUG_LOG)

        # Parse log debug/autoserv.DEBUG to find all reasons that repair failed.
        reasons = []
        debug_log = self.get_debug_log(autoserv_log_url, autoserv_log_path)

        # Some message might take multiple lines.
        error = None
        action = None
        for line in debug_log:
            if self.is_log_entry(line):
                if error:
                    reasons.append(FailureReason(action, error, hostname))
                    action = None
                if not action:
                    action = self.get_action(line)
                error = extract_match_text(line, REPAIR_FAILURE_PATTERN)
            elif error:
                error += line
        if error:
            reasons.append(FailureReason(action, error, hostname))

        # Close the stream if debug_log is not a list of string read from
        # command 'gsutil cat'.
        if not isinstance(debug_log, list):
            debug_log.close()

        return reasons


    def log(self):
        """Print the details about why DUT was failed to be repaired.
        """
        print '\nExamining failure reason for %s ...' % self.host['hostname']
        print '    Log url: %s' % self.log_url
        print '    Repair failed reasons:'
        print '\n'.join(['        ' + reason.key for reason in self.reasons])


def extract_match_text(line, pattern):
    """Extract the text information that matches the pattern.

    @param line: A single line in the log file.
    @return: Text that matches the given pattern, None if the line does not
             match the pattern.
    """
    m = pattern.match(line)
    if m:
        return m.group(1)
    else:
        return None


def log_result(result):
    print "Examining %s ..." % result.host

    if result.ping:
        print "  PING = UP"
    else:
        print "  PING = DOWN\n"
        return

    if result.ssh:
        print "  SSH = UP"
    else:
        print "  SSH = DOWN\n"
        return

    print "  SERVOD = %s" % ('UP' if result.servod else 'DOWN',)
    print "  LOGS = \n%s" % (result.logs,)


def check_servo(servo):
    r = Result(servo, None, None, None, None)

    r.ping = (utils.ping(servo, tries=5, deadline=5) == 0)
    if not r.ping:
        return r

    try:
        subprocess.check_output(ssh_command(servo, "true"))
    except subprocess.CalledProcessError:
        r.ssh = False
        return r
    else:
        r.ssh = True

    try:
        output = subprocess.check_output(ssh_command(servo, "pgrep servod"))
    except subprocess.CalledProcessError:
        r.servod = False
    else:
        r.servod = (output != "")

    try:
        output = subprocess.check_output(
            ssh_command(servo, "tail /var/log/servod.log"))
    except subprocess.CalledProcessError:
        r.logs = ""
    else:
        r.logs = output

    return r


def get_last_repair_job(afe, host):
    """Get the job ID of last repair job.

    @param afe: rpc interface.
    @param host: Attribute dictionary of host that failed to be repaired.
    @return: Job ID of last repair job.
    """
    try:
        tasks = afe.run('get_special_tasks',
                        host__hostname=host['hostname'],
                        task='Repair',
                        time_started__isnull=False,
                        is_complete=True,
                        is_aborted=False,
                        sort_by=['-time_started'],
                        query_limit=1)
        return tasks[0]['id']
    except Exception as e:
        print ('Failed to get repair job id for host %s: %s' %
               (host['hostname'], e))
        return None


def check_host_failure(input):
    """Check why host failed to be repaired.

    @param input: A dictionary of input arguments, i.e.,
                  {server, host, repair_job_id}, where:
                  server is the name of autotest instance
                  host is an attribute dictionary of host that failed to be
                      repaired.
                  repair_job_id is the job ID of last repair job.
    """
    return Failure(server=input['server'], host=input['host'],
                   repair_job_id=input['repair_job_id'])


def redeploy_hdctools(host):
    try:
        subprocess.check_output(
            ssh_command(host, "/home/chromeos-test/hdctools/beaglebone/deploy"),
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return False
    else:
        return True


def install_package(package):
    def curry(host):
        try:
            subprocess.check_output(
                ssh_command(host, "apt-get install %s" % package),
                stderr=subprocess.STDOUT)
            subprocess.check_output(
                ssh_command(host, "start servod"),
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            return False
        else:
            return True
    curry.__name__ = "install_package(%s)" % package
    return curry


def manual_intervention(reason):
    def curry(_):
          return False

    curry.__name__ = 'MANUAL(%s)' % reason
    return curry


Fix = collections.namedtuple('Fix', ['host', 'method', 'success'])

# I don't know if these failures are one-time or repeating, so I'm adding code
# here for now.  If these are seen and fixed by this frequently, then this code
# should be moved into servo_host's repair()
def diagnose_failure(r):
    method = None

    if r.logs and 'ImportError: Entry point' in r.logs:
        method = redeploy_hdctools

    if r.logs and 'ImportError: No module named serial' in r.logs:
        method = install_package('python-serial')

    if not r.ping or not r.ssh:
        method = manual_intervention('servo is unresponsive on network')

    if r.logs and 'No usb device connected to servo' in r.logs:
        method = manual_intervention("servo doesn't see USB drive")

    if r.logs and 'discover_servo - No servos found' in r.logs:
        method = manual_intervention("beaglebone doesn't see servo")

    if method:
        return Fix(r.host, method.__name__, method(r.host))
    else:
        return None


def get_board(host):
    """Get name of the board from a host object.

    @param host: An attribute dictionary of host.
    @return: Name of the board, return None if board label is not found.
    """
    for label in host['labels']:
        if label.startswith('board:'):
            return label[6:]
    return None


def main():
    pool = multiprocessing.pool.ThreadPool()
    all_results = []
    all_repair_failures = []

    for server in SERVERS:
        afe = frontend.AFE(server=server)
        hosts = afe.run('get_hosts', multiple_labels=['servo'],
                        status='Repair Failed')
        print ('%s: %s hosts with servo label are in Repair Failed.' %
               (server, len(hosts)))

        servos = [h['hostname']+'-servo.cros' for h in hosts]

        results = pool.imap_unordered(check_servo, servos)
        for result in results:
            log_result(result)
            all_results.append(result)

        inputs = [{'server': server, 'host': host,
                   'repair_job_id': get_last_repair_job(afe, host)}
                   for host in hosts]

        repair_failures = pool.imap_unordered(check_host_failure, inputs)
        for failure in repair_failures:
            failure.log()
            all_repair_failures.append(failure)

    failure_collection = []
    for failure in all_repair_failures:
        failure_collection.extend([(reason, get_board(failure.host))
                                   for reason in failure.reasons
                                   if 'servo' in reason.action])

    def compare_failure(f1, f2):
        return (cmp(f1[0].key, f2[0].key) or cmp(f1[1], f2[1]) or
                cmp(f1[0].hostname, f2[0].hostname))
    failure_collection.sort(cmp=compare_failure)
    print '====================================='
    print 'DUTs failed to be repaired by servo:'
    print '====================================='
    current_key = None
    for (reason, board) in failure_collection:
        if reason.key != current_key:
            print reason.key
            current_key = reason.key
            current_board = None
        if board != current_board:
            print '    %s' % board
            current_board = board
        print '        %s' % reason.hostname

    # fix 'em if you can?
    fixes = filter(None, pool.imap_unordered(diagnose_failure, all_results))
    for fix in fixes:
      print ("Fixing %(host)s via %(method)s resulted in %(success)s" %
             dict(host=fix.host, method=fix.method,
                  success='SUCCESS' if fix.success else 'FAILURE'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
