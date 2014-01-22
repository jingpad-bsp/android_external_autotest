#!/usr/bin/env python

import subprocess
import multiprocessing.pool

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

    if result.ping == 0:
        print "  PING = UP"
    else:
        print "  PING = DOWN"
        return

    if result.ssh:
        print "  SSH = UP"
    else:
        print "  SSH = DOWN"
        return

    print "  SERVOD = %s" % ('UP' if result.servod else 'DOWN',)
    print "  LOGS = \n%s" % (result.logs,)


def check_servo(servo):
    r = Result(servo, None, None, None, None)

    r.ping = utils.ping(servo, tries=5, deadline=5)
    if r.ping != 0:
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

for server in SERVERS:
    afe = frontend.AFE(server=server)
    hosts = afe.run('get_hosts', multiple_labels=['servo'],
                    status='Repair Failed')
    servos = [h['hostname']+'-servo.cros' for h in hosts]

    pool = multiprocessing.pool.ThreadPool()
    results = pool.imap_unordered(check_servo, servos)
    for result in results:
        log_result(result)
