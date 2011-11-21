#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""System Monitor.

This program monitors the health of Chrome OS devices in the AutoTest testbed.

  Classes:

  Monitor - The Monitor is responsible for managing the overall process of
  keeping an updated status of each host available to AutoTest.

  RemoteWorker - responsible for SSHing to remote hosts to gather resources.

  Resource - maintains all of the resources that are monitored, and methods to
  parse their data for consumption by RRDTool.

  RRD - maintains all interfaces to RRDTool, including graph definitions, and
  methods to create, update, and graph resources.

  TestBed - a global class used to hold configuration data and data collected
  from each remote host. Additionally, formatted data for RRD will be kept
  associated with each host, and some general information about the update
  process of each remote host.


Usage:
  The following options are supported:
  --webdir: Systemhealth web directory.
  --url: URL for landing page.
  --datadir: Non-NFS directory for RRD files.

  --graph: Create 1, 4, and 24 hour graphs for each host.
  --all_graphs: Create all graphs for each host.
  --html: Build HTML pages for hosts.
  --update: Collect data from hosts.
  --skip_at_status: Don't collect data about hosts from autotest CLI.
  --timout: Seconds to wait for remote commands to complete.

  --log_file: Write log messages to specified log file.
  --skip_console: Do not write log messages to the console.
  --verbose: Set the logging level to debug.

  --cli: Autotest CLI executable location.
  --acl: Autotest ACL Group to query for host machines.
  --label: Only run on hosts with the specified label.
  --status: Only run on hosts with the specified status.
  --user: Only run on hosts with the specified user.

  Arguments should be space separated.
"""

__author__ = ('kdlucas@gmail.com (Kelly Lucas) & '
              'pauldean@google.com (Paul Pendlebury)')
__version__ = '3.10'


import cPickle
import datetime
import json
import logging
import optparse
import os
import shutil
import sys
import time
import traceback

import chromeos_test_common
from chromeos_test import autotest_util
from chromeos_test import common_util
from chromeos_test import mp_log_util
from chromeos_test import mp_thread_pool as tp
import IPy


class RemoteWorker(object):
  """Obtain resource data from remote hosts using monitor_remote_worker.py."""

  def __init__(self, hostname, platform, testbed):
    """Inits RemoteWorker with hostname and test configuration.

    Args:
      hostname: string, hostname of AutoTest host.
      platform: string, platform of hostname.
      testbed: testbed object for this run.
    """
    self.h = hostname
    self.platform = platform
    self.tb = testbed

    # Set up some dictionaries for each host.
    self.host_data = {}
    self.host_data['rrddata'] = {}  # Formatted data.
    self.host_data['status'] = False
    self.host_data['time'] = None
    for v in self.tb.version:
      self.host_data[v] = {}
      self.host_data[v]['PTR'] = None

  def Run(self, logger):
    """Method called into by thread pool."""

    logger.debug('Starting host %s.', self.h)
    updated_html_needed = False
    data_file = os.path.join(self.tb.datadir, 'hosts', self.h, 'data.pkl')
    local_script = os.path.join(chromeos_test_common.CURRENT_DIR,
                                'monitor_remote_worker.py')
    remote_script = '/tmp/monitor_remote_worker.py'

    try:
      if self.tb.update:
        if not os.path.isfile(local_script):
          logger.error('Script file %s missing.', local_script)
          return

        # Copy script
        try:
          common_util.RemoteCopy(self.h, 'root', local_script, remote_script)
        except common_util.ChromeOSTestError:
          logger.error('Skipping unreachable host %s.', self.h)
          return
        # Run Script
        try:
          output = common_util.RemoteCommand(self.h, 'root', remote_script,
                                             output=True)
          self.host_data = cPickle.loads(output)
        except common_util.ChromeOSTestError:
          logger.exception('Error running script on host %s.', self.h)
          self.host_data['status'] = 'CollectionError'
      else:
        # If it exists, load saved host_data.
        if os.path.isfile(data_file):
          with open(data_file, 'rb') as in_file:
            self.host_data = cPickle.load(in_file)

      advisor = Resource()
      if ((self.tb.update or self.tb.graph) and
          self.host_data['status'] != 'CollectionError'):
        updated_html_needed = self.UpdateRelease(logger)
        advisor.ProcessHostRRD(self.h, self.host_data, self.tb, logger)
      if self.tb.html:
        advisor.BuildHTML(self.h, self.platform, self.host_data, self.tb,
                          updated_html_needed)

      # Save successful host data so it can be loaded later.
      if self.tb.update and self.host_data['status'] == 'True':
        # rrd data is no longer needed, so don't save it.
        del self.host_data['rrddata']
        self.host_data['rrddata'] = {}
        with open(data_file, 'wb') as out_file:
          cPickle.dump(self.host_data, out_file, cPickle.HIGHEST_PROTOCOL)

    # Lots of exception handling happening here. This is the entry point
    # for this thread/process and if we let an exception go unhandled
    # we wouldn't it from the main thread and we would miss any
    # notifications of problems.
    except (KeyboardInterrupt, SystemExit):
      logging.exception('Shutdown requested.')
      sys.exit(1)
    except Exception:
      logging.exception('Unexpected Exception on %s', self.h)
      raise
    logger.debug('Finished host %s.', self.h)

  def UpdateRelease(self, logger):
    """Update Release info with most current release versions.

    The PTR key points to the most recent released version. This will also
    preserve the last known release version in case the host is down.

    Args:
      logger: multiprocess logger

    Returns:
      True/False if new HTML files are needed for this host.
    """
    rrd_dir = os.path.join(self.tb.datadir, 'hosts', self.h, 'rrd')
    # Check if the host directory exists, if not create it.
    common_util.MakedirsExisting(rrd_dir)

    update_html = False
    for v in self.tb.version:
      update_file = False
      relfile = os.path.join(rrd_dir, v)
      tmpfile = os.path.join(rrd_dir, v + '.tmp')
      if os.path.isfile(relfile):
        try:
          rf = open(relfile, 'r')
          lines = rf.readlines()
        except IOError, e:
          logger.error('Parsing release file %s\n%s', relfile, e)
        finally:
          rf.close()

        for line in lines:
          fields = line.split('=')
          # The correct format will have two strings separated by =.
          if len(fields) == 2:
            if fields[0] == 'PTR':
              if self.host_data[v]['PTR']:
                if self.host_data[v]['PTR'] != fields[1]:
                  # Most recent version has changed.
                  update_file = True
                  lines.pop(lines.index(line))
                  self.host_data[v][self.tb.time] = (self.host_data[v]['PTR'])
              else:
                # Host is down so use last known value.
                self.host_data[v]['PTR'] = (fields[1].strip())
            else:
              self.host_data[v][fields[0]] = (fields[1].strip())
          elif len(line) > 3:
            # This means the release file has the wrong format, so
            # we'll just write a new one with current values.
            update_file = True
            lines.pop(lines.index(line))
          else:
            # If we get here than it's probably a blank line.
            update_file = True
            lines.pop(lines.index(line))

        if update_file:
          update_html = True
          logger.debug('Updating %s', relfile)
          shutil.move(relfile, tmpfile)
          # Put the most recent update in the new file, and make the
          # PTR key to point to it.
          lines.append('%s=%s\n' % (self.tb.time, self.host_data[v]['PTR']))
          lines.append('PTR=%s' % self.host_data[v]['PTR'])
          try:
            rf = open(relfile, 'w')
            for line in lines:
              rf.write(line)
          except IOError, e:
            logger.error('Writing %s\n%s', relfile, e)
          finally:
            rf.close()
      else:
        # Create a new release file, as it does not exist.
        if self.host_data[v]['PTR']:
          update_html = True
          logger.info('Creating new %s', relfile)
          try:
            rf = open(relfile, 'w')
            rf.write('%s=%s\n' % (self.tb.time, self.host_data[v]['PTR']))
            rf.write('PTR=%s' % self.host_data[v]['PTR'])
          except IOError, e:
            logger.error('Writing %s\n%s', relfile, e)
          finally:
            rf.close()

          self.host_data[v][self.tb.time] = (self.host_data[v]['PTR'])
    return update_html


class TestBed(object):
  """Used to hold all of the global variables."""

  def __init__(self, options):
    """Inits TestBed with run options.

    Args:
      options: Command line args for this run.
    """
    # Save run start time.
    self.time = int(time.time())

    # Setup logging.
    self.options = options
    self.logfile = options.log_file

    logger = logging.getLogger()
    mp_log_util.InitializeLogging(logger, **vars(options))

    # Warn and exit if SSH is not in the environment.
    if not 'SSH_AGENT_PID' in os.environ:
      logger.error('SSH_AGENT_PID not in environment, ssh commands will fail '
                   'to execute.')
      sys.exit(1)

    # Verify RRD is installed where we expect it.
    if not os.path.exists('/usr/bin/rrdtool'):
      logger.error('RRD is not installed to /usr/bin/rrdtool. Run \'sudo '
                   'apt-get install rrdtool\'.')
      sys.exit(1)

    # Assign TestBed values used for RRD and HTML pages.
    self.version = ['ec_firmware', 'firmware', 'release']
    self.rrdtimes = ['-1hours', '-4hours', '-24hours', '-1week', '-1month',
                     '-1year']

    # Make sure directories exist to hold status and data files.
    run_dir = os.path.normpath('/tmp/systemhealth')
    common_util.MakedirsExisting(run_dir)

    # Default status files.  Used to prevent more than one instance from
    # running at the same time.
    self.update_runfile = os.path.join(run_dir, 'update.running')
    self.graph_runfile = os.path.join(run_dir, 'graph.running')

    # Requested run actions.
    self.graph = options.graph
    self.all_graphs = options.all_graphs
    self.html = options.html
    self.update = options.update
    self.timeout = options.timeout
    self.skip_at_status = options.skip_at_status

    # Machine setup.
    self.webdir = options.webdir
    self.url = options.url
    self.datadir = options.datadir

    # Output some debug info.
    self.run_description = str(os.getpid()) + ':'
    if self.update:
      self.run_description += ' Update'
    if self.graph:
      self.run_description += ' Graph'
    if self.all_graphs:
      self.run_description += '_All'
    if self.html:
      self.run_description += ' HTML'
    if not self.skip_at_status:
      self.run_description += ' Status'
    mp_log_util.LogWithHeader('Start ' + self.run_description, logger)


class Monitor(object):
  """Main class used to manage the monitoring of remote hosts.

  This class is used to determine the current status of hosts in the AutoTest
  testbed. AutoTest will be queried to populate self.rhosts. It will populate
  a list of RemoteWorkes and submit that list to MultiProcWorkPool to query
  each host to gather resource data.
  """

  def __init__(self, testbed, options):
    """Monitor will use config data from TestBed."""
    self.tb = testbed
    self.options = options
    self.mp_wp = tp.MultiProcWorkPool()
    self.afe_hosts = autotest_util.GetHostData(self.tb.options.cli,
                                               self.tb.options.acl,
                                               self.tb.options.label,
                                               self.tb.options.user,
                                               self.tb.options.status)
    self.host_status = []

  def UpdateStatus(self):
    """Update data from all monitored hosts."""

    # Don't attempt work when no hosts are known.
    if not self.afe_hosts:
      return

    # Record known host status from Autotest
    if not self.options.skip_at_status:
      self.RecordAutotestHostStatus(self.afe_hosts)

    # Create instance of RemoteWorker class for every host from atest.
    self.host_status = [RemoteWorker(host, self.afe_hosts[host]['platform'],
                                     self.tb) for host in self.afe_hosts.keys()]

    # Submit RemoteWorker items to thread pool.
    self.host_status = self.mp_wp.ExecuteWorkItems(
        self.host_status, 'Run', provide_logger=True,
        logger_init_callback=mp_log_util.InitializeLogging,
        **vars(self.options))

    loglevel = logging.getLogger().getEffectiveLevel()
    if loglevel == logging.DEBUG:
      for worker in self.host_status:
        logging.debug('%s status is %s/%s', worker.h,
                      worker.host_data['status'],
                      self.afe_hosts[worker.h]['status'])

  def RecordAutotestHostStatus(self, hosts):
    """Record Autotest status of all hosts in rrd files.

    Args:
      hosts: Dictionary of host information from autotest cli.
    """

    # Maps a host status string to an index in an array.
    status_key = {'Repairing': 0, 'Verifying': 1, 'Repair_Failed': 2,
                  'Running': 3, 'Cleaning': 4, 'Ready': 5, 'Pending': 6}

    # lab_status holds the lab data in the format rrd needs. The special
    # netbook_ALL platform is the sum of all the platforms.
    lab_status = {'netbook_ALL': [0] * len(status_key)}

    # Loop through all the hosts recording their status in lab_status
    for host in hosts:
      status = hosts[host]['status'].replace(' ', '_')
      platform = hosts[host]['platform']

      if platform not in lab_status:
        lab_status[platform] = [0] * len(status_key)
      if status in status_key:
        lab_status[platform][status_key[status]] += 1
        lab_status['netbook_ALL'][status_key[status]] += 1
      else:
        logging.error('Status=%s not a known status of %s', status, status_key)

    Resource().ProcessAutotestRRD(lab_status, self.tb, logging.getLogger())

    # Save data for later analysis in a pickled data file.
    for platform in lab_status:
      data_folder = os.path.join(self.tb.datadir, 'hosts', platform)
      common_util.MakedirsExisting(data_folder)

      data_file = os.path.join(data_folder, 'utilization.pkl')
      platform_data = {}
      if os.path.isfile(data_file):
        with open(data_file, 'rb') as in_file:
          platform_data = cPickle.load(in_file)

      date_entry = datetime.datetime.strftime(datetime.datetime.now(),
                                              '%Y_%m_%d_%H_%M_%S')
      platform_data[date_entry] = lab_status[platform]
      with open(data_file, 'wb') as out_file:
        cPickle.dump(platform_data, out_file, cPickle.HIGHEST_PROTOCOL)

  @staticmethod
  def ValidIP(address):
    """Verify address is a valid IP address.

    Args:
      address: string.
    Returns:
      boolean: True = valid IP address, False = not valid IP address.
    """
    octets = address.split('.')
    if len(octets) != 4:
      return False
    for octet in octets:
      if not 0 <= int(octet) <= 255:
        return False
    return True

  def SortAFEHosts(self, afelist):
    """Sort AFE host list by IP address.

    Args:
      afelist: list of AFE host objects.
    Returns:
      newlist: list of sorted AFE host objects.
    """
    iplist = []
    hostlist = []

    for h in afelist:
      if self.ValidIP(h):
        iplist.append(h)
      else:
        hostlist.append(h)

    templist = [(IPy.IP(h).int(), h) for h in iplist]
    templist.sort()
    newlist = [h[1] for h in templist]
    hostlist.sort()
    newlist.extend(hostlist)

    return newlist

  def BuildLandingPage(self):
    """Build the initial HTML landing page with links to all hosts."""
    logging.debug('Building Landing Page')
    sorted_hosts = []
    downhosts = 0
    down_repair = 0
    down_running = 0
    down_ready = 0
    down_other = 0

    readyhosts = 0
    ready_repair = 0
    ready_running = 0
    ready_ready = 0
    ready_other = 0

    scripthosts = 0
    script_repair = 0
    script_running = 0
    script_ready = 0
    script_other = 0

    hostlist = self.afe_hosts.keys()
    sorted_ip = self.SortAFEHosts(hostlist)

    # Create a dictionary to easily map host name to host result.
    host_results = {}
    for host in self.host_status:
      host_results[host.h] = host

    # Put host that are down first
    for h in sorted_ip:
      insert_offset = 0
      # Up hosts.
      if host_results[h].host_data['status'] == 'True':
        readyhosts += 1
        insert_offset += downhosts + scripthosts
        if self.afe_hosts[h]['status'] == 'Repair':
          insert_offset += ready_repair
          ready_repair += 1
          self.afe_hosts[h]['color'] = '#96BAC6'
          self.afe_hosts[h]['status_string'] = 'Repair'
        elif self.afe_hosts[h]['status'] == 'Running':
          insert_offset += ready_repair + ready_running
          ready_running += 1
          self.afe_hosts[h]['color'] = '#BBD9EE'
          self.afe_hosts[h]['status_string'] = 'Running'
        elif self.afe_hosts[h]['status'] == 'Ready':
          insert_offset += ready_repair + ready_running + ready_ready
          ready_ready += 1
          self.afe_hosts[h]['color'] = '#FFFFFF'
          self.afe_hosts[h]['status_string'] = 'Ready'
        else:
          insert_offset += (ready_repair + ready_running + ready_ready +
                            ready_other)
          ready_other += 1
          self.afe_hosts[h]['color'] = '#788D9A'
          status_str = self.afe_hosts[h]['status']
          self.afe_hosts[h]['status_string'] = status_str
      # Up hosts with python problems.
      elif host_results[h].host_data['status'] == 'CollectionError':
        scripthosts += 1
        insert_offset += downhosts
        if self.afe_hosts[h]['status'] == 'Repair':
          insert_offset += script_repair
          script_repair += 1
          self.afe_hosts[h]['color'] = '#245403'
          self.afe_hosts[h]['status_string'] = 'ScriptError/Repair'
        elif self.afe_hosts[h]['status'] == 'Running':
          insert_offset += script_repair + script_running
          script_running += 1
          self.afe_hosts[h]['color'] = '#406331'
          self.afe_hosts[h]['status_string'] = 'ScriptError/Running'
        elif self.afe_hosts[h]['status'] == 'Ready':
          insert_offset += (script_repair + script_running + script_ready)
          script_ready += 1
          self.afe_hosts[h]['color'] = '#5E924E'
          self.afe_hosts[h]['status_string'] = 'ScriptError/Ready'
        else:
          insert_offset += (script_repair + script_running + script_ready +
                            script_other)
          script_other += 1
          self.afe_hosts[h]['color'] = '#183503'
          status_str = 'ScriptError/' + self.afe_hosts[h]['status']
          self.afe_hosts[h]['status_string'] = status_str
      # Down hosts.
      else:
        downhosts += 1
        if self.afe_hosts[h]['status'] == 'Repair':
          insert_offset += down_repair
          down_repair += 1
          self.afe_hosts[h]['color'] = '#867146'
          self.afe_hosts[h]['status_string'] = 'Down/Repair'
        elif self.afe_hosts[h]['status'] == 'Running':
          insert_offset += down_repair + down_running
          down_running += 1
          self.afe_hosts[h]['color'] = '#E5DCBD'
          self.afe_hosts[h]['status_string'] = 'Down/Running'
        elif self.afe_hosts[h]['status'] == 'Ready':
          insert_offset += down_repair + down_running + down_ready
          down_ready += 1
          self.afe_hosts[h]['color'] = '#D6C085'
          self.afe_hosts[h]['status_string'] = 'Down/Ready'
        else:
          insert_offset += (down_repair + down_running + down_ready +
                            down_other)
          down_other += 1
          self.afe_hosts[h]['color'] = '#4F4126'
          status_str = 'Down/' + self.afe_hosts[h]['status']
          self.afe_hosts[h]['status_string'] = status_str
      sorted_hosts.insert(insert_offset, h)

      # If we didn't connect to the host this run, load data from
      # the last successful run.
      if host_results[h].host_data['status'] != 'True':
        data_file = os.path.join(self.tb.datadir, 'hosts', h, 'data.pkl')
        if os.path.isfile(data_file):
          with open(data_file, 'rb') as in_file:
            host_results[h].host_data = cPickle.load(in_file)

    # Create symlink to the log file if it does not exist.
    log_filename = os.path.join(self.tb.webdir, 'monitor.log')
    if not os.path.isfile(log_filename):
      try:
        os.symlink(self.tb.logfile, log_filename)
      except OSError, e:
        logging.error('Linking to logfile\n%s', e)
    land_page_file = os.path.join(self.tb.webdir, 'index.html')
    # The temp file is used so that there will always be viewable html page
    # when the new page is being built.
    land_page_temp = os.path.join(self.tb.webdir, 'temp.html')
    f = open(land_page_temp, 'w')
    f.write('<HTML><HEAD>')
    f.write('<LINK REL="stylesheet" TYPE="text/css" HREF="table.css">')
    f.write('<TITLE>AutoTest System Health Check</TITLE></HEAD>')
    f.write('<BODY>')
    f.write('<img src="chrome.png" style="float:left;"/>')
    f.write('<table style="float: right">')
    f.write(('<TR><TD><a href=%s>%s</a><TD>Hosts<TD>Ready<TD>Repair<TD>'
             'Running<TD>Other') %  ('monitor.log', 'Log File'))
    f.write('<TR><TD>Total')
    f.write('<TD>%d<TD>%d<TD>%d<TD>%d<TD>%d' % (
        downhosts + readyhosts + scripthosts,
        down_ready + ready_ready + script_ready,
        down_repair + ready_repair + script_repair,
        down_running + ready_running + script_running,
        down_other + ready_other + script_other))
    f.write('<TR><TD>Inaccessible')
    f.write('<TD>%d<TD>%d<TD>%d<TD>%d<TD>%d' % (downhosts, down_ready,
                                                down_repair, down_running,
                                                down_other))
    f.write('<TR><TD>Script Error')
    f.write('<TD>%d<TD>%d<TD>%d<TD>%d<TD>%d' % (scripthosts, script_ready,
                                                script_repair, script_running,
                                                script_other))
    f.write('<TR><TD>Accessible')
    f.write('<TD>%d<TD>%d<TD>%d<TD>%d<TD>%d' % (readyhosts, ready_ready,
                                                ready_repair, ready_running,
                                                ready_other))
    f.write('</table>')
    f.write('<center><H1>CAUTOTEST Testbed</H1>')
    f.write('<H2>System Health</H2>')
    plat_graph = os.path.join(self.tb.url, 'hosts', 'netbook_ALL',
                              'utilization-24hours.png')
    f.write('<BR><BR><img src=%s ><BR><BR>' % plat_graph)
    f.write('<table>')
    f.write('<CAPTION>Hosts last updated: %s</CAPTION>' % time.strftime(
        '%d %b %Y - %I:%M:%S %p %Z', time.localtime()))
    f.write('<TR><TH>Hostname<TH>Status<TH>Labels<TH>Last Update')
    f.write('<TH>Release<TH>Health</TR>')
    for h in sorted_hosts:
      link_dir = 'hosts/' + h
      web_dir = os.path.join(self.tb.webdir, 'hosts', h)
      common_util.MakedirsExisting(web_dir, 0755)
      fqn = 'http://cautotest.corp.google.com/'
      view_host = 'afe/#tab_id=view_host&object_id=%s' % h
      hlink = fqn + view_host
      f.write('<tr bgcolor=%s><th>' % self.afe_hosts[h]['color'])
      f.write('<a href=%s>%s</a></th>' % (hlink, h))
      f.write('<td><em>%s</em>' % self.afe_hosts[h]['status_string'])
      f.write('<td>')
      f.write('<em><b>%s</b></em><br>' % self.afe_hosts[h]['platform'])
      for label in self.afe_hosts[h]['labels']:
        f.write('%s<br>' % label)
      f.write('<td>%s' % host_results[h].host_data['time'])
      if host_results[h].host_data['release']['PTR']:
        f.write('<td>%s' % host_results[h].host_data['release']['PTR'])
      else:
        f.write('<td>Unknown')
      index_file = os.path.join(web_dir, 'index.html')
      if os.path.isfile(index_file):
        f.write('<td><a href=%s' % self.tb.url)
        f.write('%s/index.html target="_blank">' % link_dir)
        f.write('health</a></td>')
      else:
        f.write('<td>None</td>')
    f.write('</table><p>\n</center>\n</BODY></HTML>')
    f.close()
    shutil.copyfile(land_page_temp, land_page_file)
    os.chmod(land_page_file, 0644)


class Resource(object):
  """Contains structures and methods to collect health data on hosts.

  For each resource in self.resources, there must also be a corresponding
  method to format the data into what RRDTool expects.
  """

  def __init__(self):
    self.resources = [
        'battery',
        'boot',
        'cpu',
        'load',
        'memory',
        'network',
        'power',
        'temp',
        'uptime'
        ]
    self.fs = [
        'rootfsA_space',
        'rootfsA_inodes',
        'rootfsA_stats',
        'rootfsB_space',
        'rootfsB_inodes',
        'rootfsB_stats',
        'stateful_space',
        'stateful_inodes',
        'stateful_stats'
        ]
    self.resources += self.fs

  @staticmethod
  def ProcessAutotestRRD(hosts, testbed, logger):
    """Process formatted data into RRD files for each host in hosts.

    Args:
      hosts: dictionary of platforms and their data for rrd.
      testbed: configuration data for this run.
      logger: logger for this process/thread.
    """
    for platform in hosts:
      rrd_dir = os.path.join(testbed.datadir, 'hosts', platform, 'rrd')
      web_dir = os.path.join(testbed.webdir, 'hosts', platform)

      common_util.MakedirsExisting(rrd_dir)
      common_util.MakedirsExisting(web_dir, 0755)

      rrd_list = []
      for v in hosts[platform]:
        rrd_list += [str(v)]

      rrd_dict = {'rrddata': {'utilization': rrd_list}}
      rrd = RRD('utilization', platform, rrd_dir, web_dir, testbed)
      if not os.path.exists(rrd.rrdfile):
        rrd.Create(logger, 600)
      rrd.Update(rrd_dict, logger)
      rrd.Graph(rrd_dict, logger, False)

  def ProcessHostRRD(self, hostname, hostdata, testbed, logger):
    """Process formatted data into RRD files for host hostname.

    Args:
      hostname: string, hostname of AutoTest host.
      hostdata: raw data from the host.
      testbed: configuration data for this run.
      logger: logger for this process/thread.
    """
    rrd_dir = os.path.join(testbed.datadir, 'hosts', hostname, 'rrd')
    web_dir = os.path.join(testbed.webdir, 'hosts', hostname)

    common_util.MakedirsExisting(rrd_dir)
    common_util.MakedirsExisting(web_dir, 0755)

    for r in self.resources:
      dk = None  # datakey only needs to be set if it's a file system.
      if r in self.fs:
        if '_space' in r:
          dk = 'fs_space'
        elif '_inode' in r:
          dk = 'fs_inode'
        elif '_stat' in r:
          dk = 'fs_stat'

      rrd = RRD(r, hostname, rrd_dir, web_dir, testbed, dk)
      if not os.path.exists(rrd.rrdfile):
        rrd.Create(logger)
      if testbed.update == True:
        logger.debug('Updating %s for host %s', r, hostname)
        rrd.Update(hostdata, logger)
      if testbed.graph:
        logger.debug('Building %s graphs for %s', r, hostname)
        rrd.Graph(hostdata, logger)

  def BuildHTML(self, hostname, platform, hostdata, testbed,
                update_needed=False):
    """Create HTML pages for to display the graphs.

    Args:
      hostname: string, hostname of AutoTest host.
      platform: string, platform of hostname.
      hostdata: raw data from the host.
      testbed: configuration data for this run.
      update_needed: new html needed, existing has wrong info.
    """
    web_dir = os.path.join(testbed.webdir, 'hosts', hostname)
    plat_dir = os.path.join(testbed.url, 'hosts', platform)
    index_file = os.path.join(web_dir, 'index.html')

    # If the index file exists, and the release info hasn't changed, skip.
    if os.path.isfile(index_file) and not update_needed:
      return

    mainindex = testbed.url + 'index.html'
    resource_list = []
    for r in self.resources:
      resource_list.append(r)
    resource_list.sort()

    html_file = {}
    for t in testbed.rrdtimes:
      html_file[t] = hostname + t + '.html'
    pathname = {}
    for name in html_file:
      pathname[name] = os.path.join(web_dir, html_file[name])

    # Create directory for html/graphs.
    common_util.MakedirsExisting(web_dir, 0755)

    # Create HTML files for each time period we are graphing.
    for path in pathname:
      f = open(pathname[path], 'w')
      f.write('<HTML><HEAD>')
      f.write('<center><TITLE>%s System Health</TITLE></HEAD>' % hostname)
      f.write('<BODY><H1>%s System Health</H1>' % hostname)
      for v in testbed.version:
        f.write('<H4>%s: %s</H4>' % (v, hostdata[v]['PTR']))
      for t in testbed.rrdtimes:
        f.write('<a href="%s">%s</a>&nbsp;<b>|</b>' % (html_file[t], t))
      f.write('<a href="%s">SystemHealth Home</a>' % mainindex)
      f.write('<p><HR>')
      plat_graph = os.path.join(plat_dir, 'utilization' + path + '.png')
      f.write('<img src=%s ><BR><BR>' % plat_graph)
      f.write('<table border=1 bgcolor=#EEEEEE>')
      newrow = True
      for r in resource_list:
        if newrow:
          f.write('<tr>')
        f.write('<td>%s<br><a href=%s.html>' % (r, r))
        f.write('<img src=%s%s.png width=475 height=250></a></td>' % (r, path))
        if newrow:
          newrow = False
        else:
          f.write('</tr>\n')
          newrow = True
      f.write('</table><p>\n')
      f.write('</center>\n')
      f.write('<H5>Last Update: %s</H5>' % hostdata['time'])
      f.write('</BODY></HTML>')
      f.close()
      os.chmod(pathname[path], 0644)
    # Set default landing page to 24-hour graphs
    if not os.path.isfile(index_file):
      os.symlink(pathname[testbed.rrdtimes[2]], index_file)

    # Create HTML files for each resource for all time periods.
    for r in resource_list:
      rrdfile = os.path.join(web_dir, r + '.html')
      f = open(rrdfile, 'w')
      f.write('<HTML><HEAD>')
      f.write('<center><TITLE>%s %s Resources</TITLE></HEAD>' % (hostname, r))
      f.write('<BODY><H1>%s %s Resources</H1>' % (hostname, r))
      for v in testbed.version:
        f.write('<H4>%s: %s</H4>' % (v, hostdata[v]['PTR']))
      f.write('<table border=5 bgcolor=#B5B5B5>')
      f.write('<tr>')
      for t in testbed.rrdtimes:
        f.write('<td><a href="#%s"><b>%s</b></a>' % (t, t))
      f.write('</table>')
      f.write('<HR>')
      f.write('<table border=1 bgcolor=#EEEEEE>')
      for t in testbed.rrdtimes:
        f.write('<tr><td><a name="%s"><img src=%s%s.png>' % (t, r, t))
        f.write('</a></td></tr>\n')
      f.write('</table><p>\n')
      f.write('</center>\n')
      f.write('<H5>Last Update: %s</H5>' % hostdata['time'])
      f.write('</BODY></HTML>')
      f.close()
      os.chmod(rrdfile, 0644)


class RRD(object):
  """The class to create and update RRD data stores and graph them.

  This class should be used to access all of the functions of RRDTool. It will
  create the data files, update them, and create graphs/charts based on that
  data. Datakey is needed when we are using the same data definitions for many
  items of the same type, like file systems.
  """

  def __init__(self, rrdname, hostname, rrd_dir, web_dir, tb, datakey=None):
    """Inits RRD class.

    Args:
      rrdname: string, item name(should match key from Resources)
      hostname: string, hostname of the machine.
      rrd_dir: string, directory for rrd files.
      web_dir: string, directory for generated graphs.
      tb: testbase object for this run.
      datakey: string, overrides which data definition to use.
    """
    self.tb = tb
    self.rrdtool = '/usr/bin/rrdtool'
    self.rrd_dir = rrd_dir
    self.web_dir = web_dir
    self.rrdname = rrdname
    self.hostname = hostname
    rrd_filename = rrdname + '.rrd'
    self.rrdfile = os.path.join(self.rrd_dir, rrd_filename)
    file_system = 'Unknown'

    if not datakey:
      datakey = rrdname
    else:
      fields = rrdname.split('_')
      if fields[0]:
        file_system = fields[0]

    self.dd = json.load(open(os.path.join(sys.path[0], 'rrd.json')))[datakey]
    self.dd['title'] %= {'host': self.hostname, 'file_system': file_system}

  def Create(self, logger, step=600):
    """Create an empty RRD file.

    Args:
      logger: Multiprocess logger.
      step: Default rrdtool step.

    Returns:
      boolean: True = Success, False = failure.
    """

    stime = int(time.time()) - 5 * 86400
    rrd_suffix = ['RRA:AVERAGE:0.5:1:576', 'RRA:AVERAGE:0.5:6:672',
                  'RRA:AVERAGE:0.5:24:732', 'RRA:AVERAGE:0.5:144:1460']

    rrd_cmd = [self.rrdtool, 'create', self.rrdfile, '--start', str(stime),
               '--step', str(step)]
    for ds in self.dd['items']:
      ds_str = 'DS:%s:%s:%s:%s:%s' % (ds, self.dd['type'], self.dd['heartbeat'],
                                      self.dd['min'], self.dd['max'])
      rrd_cmd.append(ds_str)
    rrd_cmd += rrd_suffix
    # Convert the rrd_cmd to a string with space separated commands.
    exec_str = ' '.join(rrd_cmd)
    try:
      common_util.RunCommand(exec_str)
    except common_util.ChromeOSTestError:
      logger.error('Executing: "%s".', exec_str)
      return False
    return True

  def Update(self, hostdata, logger):
    """Update an existing RRD file.

    Args:
      hostdata: dictionary of raw data from this host.
      logger: logger for this process/thread

    Returns:
      boolean: True = Success, False = errors.
    """
    if self.rrdname in hostdata['rrddata']:
      data_count = len(hostdata['rrddata'][self.rrdname])
      if data_count == 0:
        logger.debug('Key "%s" empty in hostdata for host %s.', self.rrdname,
                     self.hostname)
        return False

      if data_count < 2:
        data = 'N:' + hostdata['rrddata'][self.rrdname][0]
      else:
        data = 'N:' + ':'.join(hostdata['rrddata'][self.rrdname])
      rrd_cmd = [self.rrdtool, 'update', self.rrdfile, data]
      exec_str = ' '.join(rrd_cmd)
      try:
        common_util.RunCommand(exec_str)
      except common_util.ChromeOSTestError:
        logger.error('Executing: "%s".', exec_str)
        return False

      return True
    else:
      logger.debug('Key "%s" not found in hostdata for host %s.', self.rrdname,
                   self.hostname)
      return False

  def Graph(self, hostdata, logger, include_updates=True, file_prefix=''):
    """Create a graph of a tracked resource.

    Args:
      hostdata: Dictionary of raw data from this host.
      logger: Logger for this process/thread.
      include_updates: Include firmware update history in graphs.
      file_prefix: String to append to front of graph file names.
    """
    width = '850'
    height = '300'
    end = 'now'
    rcolor = {'release': '#9966FF', 'firmware': '#990033',
              'ec_firmware': '#009933'}

    if self.tb.all_graphs:
      rrdtimes = self.tb.rrdtimes
    else:
      rrdtimes = self.tb.rrdtimes[:3]

    for rrdtime in rrdtimes:
      png_filename = file_prefix + self.rrdname + rrdtime + '.png'
      png_file = os.path.join(self.web_dir, png_filename)

      title = self.dd['title'] + ' ' + rrdtime + '"'

      rrd_cmd = [self.rrdtool, 'graph', png_file, '--imgformat PNG', '-s',
                 rrdtime, '--end', end, '--width', width, '--height', height,
                 '--vertical-label', self.dd['units'], '--title', title]

      for ds in self.dd['items']:
        rrd_cmd.append('DEF:%s=%s:%s:AVERAGE' % (ds, self.rrdfile, ds))
      rrd_cmd += self.dd['graph']
      if include_updates:
        rrd_cmd.append('COMMENT:"Release History \\s"')
        rrd_cmd.append('COMMENT:"=============== \\n"')
        for v in self.tb.version:
          sorted_items = []
          for k in hostdata[v]:
            if k != 'PTR':
              sorted_items.append(k)
            sorted_items.sort()
          for i in sorted_items:
            # Get a date/time string to display, localtime requires
            # a float, so convert i to float.
            fw_datetime = time.strftime('%D %H\\:%M', time.localtime(float(i)))
            # Need to escape any ':' for RRDTool.
            filter_val = (hostdata[v][i].replace(':', '\\:'))
            if not self.tb.all_graphs:
              # Insert Veritical Lines for release and firmware updates.
              vrule = 'VRULE:%s%s:"%s %s=%s \\n"' % (i, rcolor[v], fw_datetime,
                                                     v, filter_val)
            else:
              # On Week + graphs, only insert release comment. There are too
              # many vertical lines on the longer graphs to make see anything
              # else.
              vrule = 'COMMENT:"%s %s=%s \\n"' % (fw_datetime, v, filter_val)
            rrd_cmd.append(vrule)

      exec_str = ' '.join(rrd_cmd)
      try:
        common_util.RunCommand(exec_str)
      except common_util.ChromeOSTestError:
        logger.error('Executing: "%s".', exec_str)
      if os.path.isfile(png_file):
        os.chmod(png_file, 0644)


def ParseArgs():
  """Parse all command line options."""
  homedir = os.environ['HOME']
  datadir = os.path.normpath('/usr/local/google/%s/systemhealth' % homedir)
  systemhealth_webdir = os.path.join(homedir, 'www', 'systemhealth')
  logfile = os.path.join(systemhealth_webdir, 'monitor.log')
  defaul_url = 'http://www/~%s/systemhealth/' % os.environ['USER']

  parser = optparse.OptionParser(version=__version__)

  # Args for describing the environment of the server machine.
  group = optparse.OptionGroup(
      parser, title='Server Configuration',
      description=('Options specifying the layout of this machine.'))
  group.add_option(
      '-w', '--webdir',
      help='Systemhealth web directory [default: %default]',
      default=systemhealth_webdir,
      dest='webdir')
  group.add_option(
      '-u', '--url',
      help='URL for landing page [default: %default]',
      default=defaul_url,
      dest='url')
  group.add_option(
      '-d', '--datadir',
      help='Non-NFS directory for RRD. [default: %default]',
      default=datadir,
      dest='datadir')
  parser.add_option_group(group)

  # Args for describing logging.
  mp_log_util.AddOptions(parser)

  # Args for selecting hosts from Autotest.
  autotest_util.AddOptions(parser)

  # Args for describing what work to perform.
  group = optparse.OptionGroup(
      parser, title='Run Configuration',
      description=('Options specifying what actions the script will perform.'))
  group.add_option(
      '--graph',
      help=('Create 1, 4, & 24 hour graphs for each host [default: %default]'),
      default=False, action='store_true', dest='graph')
  group.add_option(
      '--all_graphs',
      help='Create all graphs for each host [default: %default]',
      default=False, action='store_true', dest='all_graphs')
  group.add_option(
      '--html',
      help='Build HTML pages for hosts [default: %default]',
      default=False, action='store_true', dest='html')
  group.add_option(
      '--update',
      help='Collect data from hosts [default: %default]',
      default=False, action='store_true', dest='update')
  group.add_option(
      '--timout',
      help=('Timeout for remote commands to complete [default: %default]'),
      default=30, dest='timeout')
  group.add_option(
      '--skip_at_status',
      help=('Record the host status in autotest  [default: %default]'),
      default=False, action='store_true', dest='skip_at_status')

  parser.add_option_group(group)

  options = parser.parse_args()[0]

  if not options.log_file:
    options.log_file = logfile

  if options.all_graphs:
    options.graph = True

  if not (options.graph or options.html or options.update):
    parser.error('Must specify at least one of the --graph, --html, or '
                 '--update options.')

  # Create required directories if they don't exist.
  common_util.MakedirsExisting(options.datadir)
  common_util.MakedirsExisting(options.webdir, 0755)
  common_util.MakedirsExisting(os.path.join(options.webdir, 'hosts'), 0755)

  return options


def CheckRun(action, tb):
  """Check the run status of monitor.py, and add/remove run files.

  This function will ensure we only running one program with either the graph
  or update option.
  Args:
    action: string, indicates if monitor.py is starting or stopping.
    tb: options for this run.
  """
  if action == 'start':
    if tb.update == True:
      if os.path.isfile(tb.update_runfile):
        logging.info('Exiting, already running with update option')
        sys.exit(1)
      else:
        try:
          open(tb.update_runfile, 'w').close()
        except IOError, e:
          logging.error('Opening %s\n%s', tb.update_runfile, e)
    if tb.graph:
      if os.path.isfile(tb.graph_runfile):
        logging.info('Exiting, already running with graph option')
        sys.exit(1)
      else:
        try:
          open(tb.graph_runfile, 'w').close()
        except IOError, e:
          logging.error('Opening %s\n%s', tb.graph_runfile, e)
  elif action == 'stop':
    if tb.update == True:
      if os.path.isfile(tb.update_runfile):
        try:
          os.remove(tb.update_runfile)
        except IOError, e:
          logging.error('Removing %s\n%s', tb.update_runfile, e)
    if tb.graph:
      if os.path.isfile(tb.graph_runfile):
        try:
          os.remove(tb.graph_runfile)
        except IOError, e:
          logging.error('Removing %s\n%s', tb.graph_runfile, e)
  else:
    logging.error('Unknown option passed to CheckRun(): %s', action)
    sys.exit(1)


def main():
  start_time = time.time()
  options = ParseArgs()

  test_bed = TestBed(options)
  CheckRun('start', test_bed)
  try:
    sysmon = Monitor(test_bed, options)
    if not sysmon.afe_hosts:
      logging.error('No hosts found, nothing to do, exiting.')
      sys.exit(1)
    sysmon.UpdateStatus()
    if test_bed.update:
      sysmon.BuildLandingPage()

    runtime = time.time() - start_time
    msg = 'End [ %s ] Runtime %d seconds' % (test_bed.run_description, runtime)
    mp_log_util.LogWithHeader(msg, symbol='-')

  except (KeyboardInterrupt, SystemExit):
    logging.error('Shutdown requested.')
    sys.exit(1)
  except Exception, e:
    logging.error('Exception: %s\n%s', e, traceback.format_exc())
    raise
  finally:
    CheckRun('stop', test_bed)
    os.chmod(options.log_file, 0755)

if __name__ == '__main__':
  main()
