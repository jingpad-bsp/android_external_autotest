#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Monitor Remote Worker.

This program gathers statistics from a Chromium device.

  Classes:

  HostWorker - responsible for gathering host resources.

  Resource - maintains all of the resources that are monitored, and methods to
  parse their data for consumption by RRDTool.

"""

__author__ = ('kdlucas@gmail.com (Kelly Lucas) & '
              'pauldean@google.com (Paul Pendlebury)')
__version__ = '1.00'


import cPickle
import logging
import subprocess
import sys
import time
import traceback


class HostWorker(object):
  """Obtain host resource data."""

  def __init__(self):
    """Inits HostWorker."""
    self.logger = logging.getLogger()
    self.version = ['ec_firmware', 'firmware', 'release']

    # Set up some data dictionaries
    self.host_data = {}
    self.host_data['data'] = {}  # Raw data from hosts.
    self.host_data['rrddata'] = {}  # Formatted data.
    self.host_data['status'] = 'True'
    self.host_data['time'] = None

    for v in self.version:
      self.host_data[v] = {}
      self.host_data[v]['PTR'] = None

  def Run(self):
    """Main class method to gather host resources."""

    try:
      self.host_data['time'] = time.strftime('%d%b%Y %H:%M:%S',
                                             time.localtime())
      self.ReadRelease()
      self.ReadFirmware()
      self.ReadResources()
    except (KeyboardInterrupt, SystemExit):
      self.logger.exception('Shutdown requested.')
      sys.exit(1)
    except Exception:
      self.logger.exception('Unexpected Exception.')
      raise

  def ReadRelease(self):
    """Get the Chrome OS Release version.

    The PTR key in host_data['release'] will mark the current version.
    """
    # Use grep to find the one line in the file we are after.
    cmd = ('grep CHROMEOS_RELEASE_DESCRIPTION /etc/lsb-release')
    output = ExecuteCommand(cmd)
    if output[0] == 0:
      if 'CHROMEOS_RELEASE_DESCRIPTION' in output[1]:
        release = output[1].split('=')
        self.host_data['release']['PTR'] = release[1].strip()

  def ReadFirmware(self):
    """Get the Firmware versions.

    The PTR key in host_data['ec_firmware'] and host_data['firmware'] will
    mark the current versions.
    """
    # Use grep to return the two segments of the string we are after.
    # Message 'Unable to auto-detect platform. Limited functionality only.'
    # is showing up on StandardError, so redirect that to /dev/null.
    cmd = ('/usr/sbin/mosys -k smbios info bios 2>/dev/null | '
           'grep -o \'[ec_]*version=\\"[^ ]*\\"\'')
    output = ExecuteCommand(cmd)
    if output[0] == 0:
      lines = output[1].split()
      for item in lines:
        if 'ec_version' in item:
          fields = item.split('=')
          # We must sanitize the string for RRDTool.
          val = fields[1].strip('\n" ')
          self.host_data['ec_firmware']['PTR'] = val
        elif 'version' in item:
          fields = item.split('=')
          val = fields[1].strip('\n" ')
          self.host_data['firmware']['PTR'] = val

  def ReadResources(self):
    """Get resources that we are monitoring on the host.

    Combine all the individual commands to execute into one large command
    so only one SSH connection to the host is required instead of an
    individual connection for each command in advisor.resources.
    """
    advisor = Resource()
    # Get the individual commands from the Resource class.
    cmds = advisor.GetCommands(self.logger)
    for r in advisor.resources:
      output = ExecuteCommand(cmds[r])
      if output[0] == 0:
        self.host_data['data'][r] = output[1]
    advisor.FormatData(self.host_data, self.logger)


class Resource(object):
  """Contains structures and methods to collect health data on hosts.

  For each resource in self.resources, there must also be a corresponding
  method to format the data into what RRDTool expects.
  """

  def __init__(self):
    self.files = {'battery': '/proc/acpi/battery/BAT?/state',
                  'boot': ('/tmp/firmware-boot-time'
                           ' /tmp/uptime-login-prompt-ready'),
                  'cpu': '/proc/stat',
                  'load': '/proc/loadavg',
                  'memory': '/proc/meminfo',
                  'network': '/proc/net/dev',
                  'power': '/proc/acpi/processor/CPU0/throttling',
                  'temp': '/proc/acpi/thermal_zone/*/temperature',
                  'uptime': '/proc/uptime',
                 }
    self.fs = {'rootfsA_space': '/',
               'rootfsA_inodes': '/',
               'rootfsA_stats': 'sda2 ',
               'rootfsB_space': '/',
               'rootfsB_inodes': '/',
               'rootfsB_stats': 'sda5 ',
               'stateful_space': '/mnt/stateful_partition',
               'stateful_inodes': '/mnt/stateful_partition',
               'stateful_stats': 'sda1 ',
              }
    self.resources = []
    for k in self.files:
      self.resources.append(k)
    for k in self.fs:
      self.resources.append(k)

  def FormatData(self, hostdata, logger):
    """Convert collected data into the correct format for RRDTool.

    Args:
      hostdata: raw data from the host.
      logger: logger for this process/thread.
    """

    parse_method = {'battery': self.ParseBattery,
                    'boot': self.ParseBoot,
                    'fs': self.ParseFS,
                    'diskstats': self.ParseDiskStats,
                    'cpu': self.ParseStat,
                    'load': self.ParseLoadAvg,
                    'memory': self.ParseMemInfo,
                    'network': self.ParseNetDev,
                    'power': self.ParsePower,
                    'temp': self.ParseTemp,
                    'uptime': self.ParseUpTime,
                   }

    # method_key is used here because multiple resource keys will use the
    # same method to parse them.
    for key in hostdata['data']:
      method_key = key
      if key in self.fs:
        if '_space' in key:
          method_key = 'fs'
        elif '_inode' in key:
          method_key = 'fs'
        elif '_stats' in key:
          method_key = 'diskstats'
        else:
          logger.error('Invalid key "%s".', key)
      if method_key in parse_method:
        if hostdata['data'][key]:
          parse_method[method_key](key, hostdata)
        else:
          logger.debug('%s missing from hostdata.', key)
      else:
        logger.error('No method to parse resource %s', key)

  @staticmethod
  def ParseBattery(k, hostdata):
    """Convert /proc/acpi/battery/BAT0/state to a list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    We only care about the values corresponding to the rrdkeys, so the other
    values will be discarded.
    """
    rrdkeys = ['charging state', 'present rate', 'remaining capacity']
    hostdata['rrddata'][k] = []
    statlist = hostdata['data'][k].split('\n')
    for stat in statlist:
      for key in rrdkeys:
        if key in stat:
          stats = stat.split(':')
          temp = stats[1].split()
          if key == 'charging state':
            if temp[0] == 'discharging':
              hostdata['rrddata'][k].append('0')
            else:
              hostdata['rrddata'][k].append('1')
          else:
            hostdata['rrddata'][k].append(temp[0])

  @staticmethod
  def ParseBoot(k, hostdata):
    """Parse /tmp/uptime-login-prompt-ready for boot time.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    We only want the first and 2nd values from the raw data.
    """
    fields = []
    hostdata['rrddata'][k] = []
    lines = hostdata['data'][k].split('\n')
    for line in lines:
      if not '==>' in line:
        fields.extend(line.split())
    hostdata['rrddata'][k] = fields[0:2]

  @staticmethod
  def ParseFS(k, hostdata):
    """Convert file system space and inode readings to a list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    hostdata['rrddata'][k] = []
    lines = hostdata['data'][k].split('\n')
    for line in lines:
      if not line.startswith('Filesystem'):
        fields = line.split()
        if len(fields) > 4:
          hostdata['rrddata'][k].append(fields[2])
          hostdata['rrddata'][k].append(fields[3])

  @staticmethod
  def ParseDiskStats(k, hostdata):
    """Parse read and write sectors from /proc/diskstats to list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    hostdata['rrddata'][k] = []
    fields = hostdata['data'][k].split()
    if len(fields) > 9:
      hostdata['rrddata'][k].append(fields[5])
      hostdata['rrddata'][k].append(fields[9])

  @staticmethod
  def ParseStat(k, hostdata):
    """Convert /proc/stat to lists for CPU usage.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    lines = hostdata['data'][k].split('\n')
    for line in lines:
      if 'cpu ' in line:
        vals = line.split()
        hostdata['rrddata'][k] = vals[1:5]

  @staticmethod
  def ParseLoadAvg(k, hostdata):
    """Convert /proc/loadavg to a list of strings to monitor.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    Process ID is discarded, as it's not needed.
    """
    statlist = hostdata['data'][k].split()
    hostdata['rrddata'][k] = statlist[0:3]

  @staticmethod
  def ParseMemInfo(k, hostdata):
    """Convert specified fields in /proc/meminfo to a list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    hostdata['rrddata'][k] = []
    mem_keys = ['MemTotal', 'MemFree', 'Buffers', 'Cached', 'SwapTotal',
                'SwapFree']
    lines = hostdata['data'][k].split('\n')
    for line in lines:
      for key in mem_keys:
        if key in line:
          if not 'SwapCached' in line:
            fields = line.split()
            hostdata['rrddata'][k].append(fields[1])

  @staticmethod
  def ParseNetDev(k, hostdata):
    """Convert /proc/net/dev to a list of strings of rec and xmit values.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    net_keys = ['eth0', 'wlan0']
    rrdlist = ['0', '0', '0', '0']
    lines = hostdata['data'][k].split('\n')
    for key in net_keys:
      for line in lines:
        if key in line:
          # The following routine will ensure that the values are
          # placed in the correct order in case there is an expected
          # interface is not present.
          index = net_keys.index(key)
          if index:
            index *= 2
          data = line.split(':')[1]
          fields = data.split()
          rrdlist[index] = fields[0]
          rrdlist[index + 1] = fields[8]

    hostdata['rrddata'][k] = rrdlist

  @staticmethod
  def ParsePower(k, hostdata):
    """Convert /proc/acpi/processor/CPU0/throttling to power percentage.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    hostdata['rrddata'][k] = []
    lines = hostdata['data'][k].split('\n')
    for line in lines:
      line = line.strip()
      if line.startswith('*'):
        fields = line.split(':')

    if 'fields' in locals():
      if len(fields) > 1:
        percent = fields[1].strip('%')
        percent = percent.strip()
        hostdata['rrddata'][k].append(percent)

  @staticmethod
  def ParseTemp(k, hostdata):
    """Convert temperature readings to a list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    """
    hostdata['rrddata'][k] = []
    statlist = hostdata['data'][k].split()
    if len(statlist) > 1:
      hostdata['rrddata'][k].append(statlist[1])

  @staticmethod
  def ParseUpTime(k, hostdata):
    """Convert /proc/uptime to a list of strings.

    Args:
      k: string, resource key.
      hostdata: dictionary of raw data from this host.
    Returns:
      list of strings.
    """

    hostdata['rrddata'][k] = hostdata['data'][k].split()

  def GetCommands(self, logger):
    """Routine for gathering data from files and file systems.

    Args:
      logger: multiprocess logger.

    Returns:
      dictionary of commands to run on hosts.
    """

    command = {}

    for r in self.resources:
      if r in self.files:
        if r == 'boot':
          command[r] = 'head %s' % self.files[r]
        else:
          command[r] = 'cat %s' % self.files[r]
      elif r in self.fs:
        if '_space' in r:
          command[r] = 'df -lP %s' % self.fs[r]
        elif '_inode' in r:
          command[r] = 'df -iP %s' % self.fs[r]
        elif '_stat' in r:
          command[r] = 'cat /proc/diskstats | grep %s' % self.fs[r]
        else:
          logger.error('Invalid key "%s".', r)
    return command


def ExecuteCommand(cmd):
  """Execute a command.

  Args:
    cmd: command string to run

  Returns:
    tuple(command return code, standard out, standard error)

    Note: If the command throws an OSError or ValueError the return code will
      be -1 and standard out will have the exception traceback.
  """
  try:
    proc = subprocess.Popen(cmd, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
  except OSError, e:
    logging.exception('OSError on cmd=%s.', cmd)
    return (-1, traceback.format_exc(), str(e))
  except ValueError, e:
    logging.exception('ValueError on cmd=%s.', cmd)
    return (-1, traceback.format_exc(), str(e))

  return (proc.returncode, stdout, stderr)


def main():
  """Gather host information and return data to monitor on the server."""
  logging.basicConfig(level=logging.INFO, strem=sys.stderr)

  try:
    worker = HostWorker()
    worker.Run()

    # Remove the raw data, leave the formatted data.
    del worker.host_data['data']

    # Serialize to Stdout, Monitory.py will read this into host_data[].
    print cPickle.dumps(worker.host_data)

  except (KeyboardInterrupt, SystemExit):
    logging.exception('Shutdown requested.')
    sys.exit(1)
  except Exception, e:
    logging.exception('Exception: %s\n%s', e, traceback.format_exc())
    raise


if __name__ == '__main__':
  main()
