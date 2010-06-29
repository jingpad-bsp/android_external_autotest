#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may abtain a copy of the license at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""System Monitor.

This program monitors the health of Chrome OS devices in the AutoTest testbed.

Classes:

  Monitor - The Monitor is responsible for managing the overall process of
  keeping an updated status of each host available to AutoTest.

  SSH - a very small threaded class that will ssh into a host using the paramiko
  library.

Usage:
  The following options are supported:
  --debug: set the debug level. Requires one of the following parameters:
      debug
      info (default)
      warning
      error
      critical
  --logfile: set the file name of the log file. Default: monitor.log

  Arguments should be space separated.
"""

__author__ = 'kdlucas@gmail.com (Kelly Lucas)'
__version__ = '1.0'

import logging, optparse, os, paramiko, Queue, subprocess, sys, threading
import common

settings = 'autotest_lib.frontend.settings'
os.environ['DJANGO_SETTINGS_MODULE'] = settings

from autotest_lib.frontend.afe import models as afe_models

# The following objects are variables are shared between classes.
tb = {}  # Holds autotest host's status and monitor data.
TIMEOUT = 10  # Timeout value (in seconds) for ops involving remote hosts.


def SetLogger(namespace, logfile, loglevel):
    """Create a log handler and set log level.

    Args:
        namespace: name of the logger.
        logfile: log file name.
        loglevel: debug level of logger.
    Returns:
        Logger object.
    """

    levels = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL,
             }

    logger = logging.getLogger(namespace)
    c = logging.StreamHandler()
    h = logging.FileHandler(logfile)
    hf = logging.Formatter('%(asctime)s %(process)d %(levelname)s: %(message)s')
    cf = logging.Formatter('%(levelname)s: %(message)s')
    logger.addHandler(h)
    logger.addHandler(c)
    h.setFormatter(hf)
    c.setFormatter(cf)

    logger.setLevel(levels.get(loglevel, logging.INFO))

    return logger


class SSH(threading.Thread):
    """Class used to ssh to remote hosts and collect data."""

    def __init__(self, host_q, update_q, logger, src_location):
        """Init SSH Class and set some initial attributes.

        Args:
            host_q: Queue() object of AutoTest hosts to check health.
            update_q: Queue() object of AutoTest hosts after it's checked.
            logger: initialized logger object.
            src_location: pathname of chrome os source code.
        """
        self.host_q = host_q
        self.update_q = update_q
        threading.Thread.__init__(self)
        cros_keys = 'scripts/mod_for_test_scripts/ssh_keys'
        self.privkey = os.path.join(src_location, cros_keys, 'testing_rsa')
        self.logger = logger


    def run(self):
        while True:
            host = self.host_q.get()
            if host is None:
                break # reached end of queue
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(host.hostname, username='root',
                               key_filename=self.privkey, timeout=TIMEOUT)
                tb[host.hostname]['status'] = True
                client.close()
            except Exception, e:
                self.logger.error('Host %s: %s', host.hostname, e)
                tb[host.hostname]['status'] = False

            self.host_q.task_done()
            # Now that we have an updated status, add host object to update
            # queue, which will send updates to AutoTest.
            self.update_q.put(host)


class Monitor(object):
    """Main class used to manage the monitoring of remote hosts.

    This class is used to determine the current status of hosts in the AutoTest
    testbed. AutoTest will be queried to populate self.rhosts. It will populate
    a Queue and start a threaded operation using SSH class, to access each host
    in the AutoTest testbed to determine their status, and then update AutoTest.
    """

    def __init__(self, logfile, debug_level, source):
        """Init Monitor object with necessary attributes.

        Args:
            logfile: string, name of logfile.
            debug_level: string, sets the log debug level.
        """
        self.logger = SetLogger('SystemMonitor', logfile, debug_level)
        self.src = source
        self.thread_num = 10  # Number of parallel operations.
        self.host_q = Queue.Queue()  # Queue for checking hosts.
        self.update_q = Queue.Queue()  # Queue for updating AutoTest.
        self.afe_hosts = []  # List of AutoTest host objects.
        self.GetHosts()


    def GetHosts(self):
        """Get a list of hosnames from the AutoTest server."""
        # We need to refine the list of afe_hosts.
        # self.afe_hosts are host objects from AutoTest afe models.
        self.afe_hosts = afe_models.Host.objects.extra(
            where=['status in ("Ready", "Repair Failed")'])

        for host in self.afe_hosts:
            tb[host.hostname] = {}


    def _UpdateAutoTest(self, host):
        """Update the Status of hosts on the AutoTest Server.

        Args:
            host: AutoTest host object.
        """

        if not tb[host.hostname]['status']:
            host.status = 'Repair Failed'
        else:
            host.status = 'Ready'
        host.save()


    def UpdateStatus(self):
        """Update status of all monitored hosts."""

        # Create new threads of class SSH.
        for i in range(self.thread_num):
            t = SSH(self.host_q, self.update_q, self.logger, self.src)
            t.setDaemon(True)
            t.start()

        # Fill the request queue with hostnames.
        for host in self.afe_hosts:
            self.logger.debug('Putting %s in queue', host.hostname)
            self.host_q.put(host)

        # queue.get() will block until it gets an item.
        host = self.update_q.get()
        while host:
            self.logger.debug('Updating %s on AutoTest', host)
            self._UpdateAutoTest(host)
            try:
                # queue.get() will block until timeout is reached.
                host = self.update_q.get(block=True, timeout=TIMEOUT)
            except Queue.Empty:
                break

        for host in self.afe_hosts:
            self.logger.info('%s status is %s', host.hostname,
                             tb[host.hostname]['status'])


    def CheckStatus(self, hostname):
        """Check the status of one host.

        Args:
            hostname: hostname or ip address of host to check.
        This method is primarily used for debugging purposes.
        """
        t = SSH(self.host_q, self.update_q, self.logger, self.src)
        t.setDaemon(True)
        t.start()

        for host in self.afe_hosts:
            if host.hostname == hostname:
                self.host_q.put(host)
                break

        host = self.update_q.get()
        self._UpdateAutoTest(host)
        self.logger.info('%s status is %s', host.hostname,
                         tb[host.hostname]['status'])


def ParseArgs():
    """Parse all command line options."""
    # Assume Chrome OS source is located on /usr/local/google.
    homedir = os.environ['HOME']
    cros_src = '/usr/local/google' + homedir + '/chromeos/chromeos/src'

    parser = optparse.OptionParser(version= __version__)
    parser.add_option('--debug',
                      help='Set the debug level [default: %default]',
                      type='choice',
                      choices=['debug', 'info', 'warning', 'error',
                               'critical',],
                      default='info',
                      dest='debug')
    parser.add_option('--logfile',
                      help='name of logfile [default: %default]',
                      default='monitor.log',
                      dest='logfile')
    parser.add_option('--gclient',
                      help='pathname of Chrome OS source [default: %default]',
                      default=cros_src,
                      dest='gclient')

    return parser.parse_args()


def main(argv):
    options, args = ParseArgs()
    sysmon = Monitor(options.logfile, options.debug, options.gclient)
    sysmon.UpdateStatus()


if __name__ == '__main__':
    main(sys.argv)
