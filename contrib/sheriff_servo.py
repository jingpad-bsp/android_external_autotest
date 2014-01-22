#!/usr/bin/env python

import collections
import multiprocessing.pool
import subprocess
import sys

import common
from autotest_lib.server import frontend
from autotest_lib.server import utils


SERVERS = ['cautotest', 'cautotest-cq']


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


def main():
    pool = multiprocessing.pool.ThreadPool()
    all_results = []

    for server in SERVERS:
        afe = frontend.AFE(server=server)
        hosts = afe.run('get_hosts', multiple_labels=['servo'],
                        status='Repair Failed')
        servos = [h['hostname']+'-servo.cros' for h in hosts]

        results = pool.imap_unordered(check_servo, servos)
        for result in results:
            log_result(result)
            all_results.append(result)

    # fix 'em if you can?
    fixes = filter(None, pool.imap_unordered(diagnose_failure, all_results))
    for fix in fixes:
      print ("Fixing %(host)s via %(method)s resulted in %(success)s" %
             dict(host=fix.host, method=fix.method,
                  success='SUCCESS' if fix.success else 'FAILURE'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
