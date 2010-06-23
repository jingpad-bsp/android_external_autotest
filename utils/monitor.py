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
__version__ = '0.9'

import logging, optparse, os, paramiko, Queue, subprocess, sys, threading
import common

settings = 'autotest_lib.frontend.settings'
os.environ['DJANGO_SETTINGS_MODULE'] = settings

from autotest_lib.frontend.afe import models as afe_models

# The following objects are variables are shared between classes.
tb = {}  # Holds autotest host's status and monitor data.


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
    """Class used to ssh to remote hosts and collect data.

    Args:
        rhostst_queue: a Queue object.
        logger: a logger object.
    """
    def __init__(self, rhost_queue, logger):
        self.queue = rhost_queue
        threading.Thread.__init__(self)
        self.privkey = '/home/autotest/.ssh/id_rsa'
        self.logger = logger


    def run(self):
        while True:
            rhost = self.queue.get()
            if rhost is None:
                break # reached end of queue
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(rhost, username='root',
                               key_filename=self.privkey, timeout=10)
                tb[rhost]['status'] = True
                client.close()
            except Exception, e:
                self.logger.error('Host %s: %s', rhost, e)
                tb[rhost]['status'] = False

            self.queue.task_done()


class Monitor(object):
    """Main class used to manage the monitoring of remote hosts.

    This calls is used to determine the current status of hosts in the AutoTest
    testbed. AutoTest will be queried to populate self.rhosts. It will populate
    a Queue and start a threaded operation, and ssh into each host to determine
    if it is in a 'Ready' state, and will then update AutoTest.

    Args:
        logfile: string, name of logfile.
        debug_level: string, sets the log debug level.
    """

    def __init__(self, logfile, debug_level):
        self.logger = SetLogger('SystemMonitor', logfile, debug_level)
        self.rhosts =  []  # List of remote hosts to monitor.
        self.thread_num = 10  # Number of parallel operations.
        self.queue = Queue.Queue()
        self.afe_hosts = []
        self.GetHosts()


    def GetHosts(self):
        """Get a list of hosnames from the AutoTest server."""
        # We need to refine the list of afe_hosts.
        # self.afe_hosts are host objects from AutoTest afe models.
        self.afe_hosts = afe_models.Host.objects.extra(
            where=['status in ("Ready", "Repair Failed")'])

        for h in self.afe_hosts:
            self.rhosts.append(h.hostname)
            tb[h.hostname] = {}


    def _UpdateAutoTest(self):
        """Update the Status of hosts on the AutoTest Server."""

        for h in self.afe_hosts:
            if not tb[h.hostname]['status']:
                h.status = 'Repair Failed'
            else:
                h.status = 'Ready'
            h.save()


    def UpdateStatus(self):
        """Update status of all monitored hosts."""

        # Create new threads of class SSH.
        for i in range(self.thread_num):
            t = SSH(self.queue, self.logger)
            t.setDaemon(True)
            t.start()

        # Fill the request queue with hostnames.
        for rhost in self.rhosts:
            self.logger.debug('Putting %s in queue', rhost)
            self.queue.put(rhost)

        self.queue.join()

        for rhost in self.rhosts:
            self.logger.info('%s status is %s', rhost, tb[rhost]['status'])

        self._UpdateAutoTest()


    # GetStatus is a helper function used to check one host when debugging.
    # Useful when monitor is loaded as a module in an interactive session.
    def GetStatus(self, rhost):
        """Get and update status of a given rhost.

        Args:
            rhost: string, hostname or IPaddress of monitored host.
        """

        t = SSH(self.queue, self.logger)
        t.setDaemon(True)
        t.start()
        self.queue.put(rhost)
        self.queue.join()
        self.logger.info('%s status is %s', rhost, tb[rhost]['status'])


def ParseArgs():
    """Parse all command line options."""
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

    return parser.parse_args()


def main(argv):
    options, args = ParseArgs()
    sysmon = Monitor(options.logfile, options.debug)
    sysmon.UpdateStatus()


if __name__ == '__main__':
    main(sys.argv)
