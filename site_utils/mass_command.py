#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Executes on all unlocked hosts in Autotest lab in parallel at a given rate.

Used to run a command or script on all hosts, or only those of a given platform,
in the Autotest lab.  Allows a configurable number of commands to be started in
parallel.
"""


import datetime
import logging
import optparse
import os
import time

import chromeos_test_common
from chromeos_test import autotest_util
from chromeos_test import common_util
from chromeos_test import mp_log_util
from chromeos_test import mp_thread_pool as tp

# Default number of hosts to run command/script in parallel.
DEFAULT_CONCURRENCY = 64

# Default number of hosts to update in parallel.
DEFAULT_UPDATE_CONCURRENCY = 24

# Default location of ChromeOS checkout.
DEFAULT_GCLIENT_ROOT = '/usr/local/google/home/${USER}/chromeos'

# Default path for individual host logs. Each host will have it's own file. E.g.
# <default_log_path>/<host>.log
DEFAULT_LOG_PATH = ('/tmp/mass_command_logs/%s/'
                    % time.strftime('%Y-%m-%d-%H-%M', time.localtime()))

# Default root path on remote device to copy scripts to
DEFAULT_REMOTE_COPY_PATH = '/tmp/'

# Amount of seconds to wait before declaring an command/script has failed.
DEFAULT_TIMEOUT = 120

# Amount of seconds to wait before declaring an update has failed.
DEFAULT_UPDATE_TIMEOUT = 2400


def ExecuteTask(failure_desc):
  """Decorator for try/except/log pattern for reporting status and failures.

  Args:
    failure_desc: Simple string description of task.

  Returns:
    Decorator function to wrap a method call.
  """

  def DecoratorFunc(func):
    """Function that takes the user called method as an argument."""

    def WrappedFunc(self, *args):
      """Function that wraps and executes user called method.

      Args:
        self: Self object of the class method called by decorator.
        args: Arguments to user called method.

      Returns:
        True/False if user called method succeeded.
      """
      try:
        output = func(self, *args)
        if output:
          if self.output:
            self.output += '\n' + output
          else:
            self.output = output
      except common_util.ChromeOSTestError:
        if self.logger:
          self.logger.exception('Failed running %s %s.', self.host,
                                failure_desc)
        self.result = failure_desc
        return False
      return True

    return WrappedFunc
  return DecoratorFunc


class HostWorker(object):
  """Responsible for ssh-test, locking, executing, and unlocking a host."""

  def __init__(self, host, options):
    """Create instance to perform work on a host.

    Args:
      host: IP address of the host to connect to.
      options: Command line options.
    """
    self.host = host
    self.options = options
    self.result = None
    self.output = None
    self.logger = None

  def Execute(self, logger=None):
    """Callback method to execute the requested action on the host.

    Usual sequence is to test connectivity by SSH-ing to the host, locking
    the host in Autotest, running the command, then unlocking the host.

    Args:
      logger: optional logger.

    Sets:
      self.result to 'PASS' or failure ['SSH', 'LOCK', 'COPY', 'CMD', 'URL'].
      self.output to standard out of command.
    """
    try:
      if logger:
        # Store logger in self.logger so it is accessible in ExecuteTask.
        self.logger = logger
        logger.info('Executing for host %s', self.host)

      if not self.options.skip_ssh:
        if not self.PingHost():
          return

      if self.options.lock:
        if not self.LockUnlockHost(True):
          return

      # Now that the host may be locked in Autotest the rest of the loop will
      # execute in a try/finally to make sure the host is still unlocked if
      # any of the remaining steps throw an exception.
      try:
        if self.options.url:
          if not self.ImageHost():
            return
        else:
          cmd = self.options.cmd
          if self.options.script:
            cmd = self.options.remote_file
            if not self.CopyToDevice():
              return
          if not self.SSHCmdOnHost(cmd, self.options.extra_args):
            return
      finally:
        if self.options.lock:
          self.LockUnlockHost(False)

      self.result = 'PASS'
      self.ProcessResult()

    finally:
      # Loggers hold a thread lock which cannot be pickled, so it must be
      # cleared before returning.
      self.logger = None

  def ProcessResult(self):
    """Dump the results to the screen and/or log file."""
    if self.logger:
      msg = [self.host, ' finished with ', self.result]

      if self.options.echo_output:
        if self.output:
          msg += ['\nStdOut=[\n', self.output, '\n]']
      self.logger.info(''.join(msg))

    if not self.options.no_log_files:
      log = open(os.path.join(self.options.log_path, self.host + '.log'), 'w')
      log.write(self.output)
      log.close()

  @ExecuteTask('SSH')
  def PingHost(self):
    """Tests if the requested host is reachable over SSH."""
    msg = 'Failed to ssh to host=%s' % self.host
    return common_util.RemoteCommand(self.host, 'root', 'true', error_msg=msg,
                                     output=True)

  @ExecuteTask('CMD')
  def SSHCmdOnHost(self, command, args=None):
    """Executes a command on the target host using an SSH connection.

    Args:
      command: Command to run.
      args: Extra arguments to main command to run on the remote host.

    Returns:
      String output from the command.
    """
    cmd = '"%s %s"' % (command, args)
    msg = 'Failed to run command=%s' % cmd
    return common_util.RemoteCommand(self.host, 'root', cmd, error_msg=msg,
                                     output=True)

  @ExecuteTask('COPY')
  def CopyToDevice(self):
    """Copies a file (usually a script file) to a host using scp.

    Returns:
      String output from the command.
    """
    msg = 'Failed to copy %s to root@%s:%s'% (self.options.script, self.host,
                                              self.options.remote_file)
    return common_util.RemoteCopy(self.host, 'root', self.options.script,
                                  self.options.remote_file, error_msg=msg,
                                  output=True)

  @ExecuteTask('URL')
  def ImageHost(self):
    """Uses the image_to_live script to update a host.

    Returns:
      String output from the command.
    """
    cmd = ('/usr/local/scripts/alarm %d %s/src/scripts/image_to_live.sh '
           '--update_url %s --remote %s' % (self.options.timeout,
                                            self.options.gclient,
                                            self.options.url, self.host))
    return common_util.RunCommand(cmd, output=True)

  @ExecuteTask('LOCK')
  def LockUnlockHost(self, lock=True):
    """Locks a host using the atest CLI.

    Locking a host tells Autotest that the host shouldn't be scheduled for
    any other tasks. Returns true if the locking process was successful.

    Args:
      lock: True=lock the host, False=unlock the host.

    Returns:
      String output from the command.
    """
    if lock:
      cmd = '%s host mod -l %s' % (self.options.cli, self.host)
    else:
      cmd = '%s host mod -u %s' % (self.options.cli, self.host)
    return common_util.RunCommand(cmd, output=True)


class CommandManager(object):
  """Executes a command on all of the selected remote hosts.

  The hosts are selected from Autotest using the parameters supplied on the
  command line.
  """

  def __init__(self):
    self.options = self.ParseOptions()
    mp_log_util.InitializeLogging(**vars(self.options))
    if self.options.ip_addr:
      self.host_list = [self.options.ip_addr]
    else:
      self.host_list = autotest_util.GetHostList(self.options.cli,
                                                 self.options.acl,
                                                 self.options.label,
                                                 self.options.user,
                                                 self.options.status)

  @staticmethod
  def ParseOptions():
    """Grab the options from the command line."""

    parser = optparse.OptionParser(
        'Used to run a command or script or update on all hosts, or only those '
        'of a given platform, in the Autotest lab.  Allows a configurable '
        'number of commands to be started in parallel.\n\n'
        '\texample: %prog [options] command\n\n'
        'Arguments after command are interpreted as arguments to the command.\n'
        '\n\texample: %prog [options] command [cmd_arg_1] [cmd_arg_2]\n\n'
        'Multiple command can be run by enclosing them in quotation marks.\n\n'
        '\texample: %prog [options] "command1; command2; command2"\n\n'
        'When using the --script option, additional arguments are interpreted '
        'as script options and are passed to the script after being copied to '
        'the remote device.\n\n'
        '\texample: %prog [options] --script /path/to/script.sh '
        '[script_arg_1] [script_arg_2] [script_arg_3]\n\n'
        'When using the --url option specify the path to the new build. '
        'Additional arguments are ignored.\n\n'
        '\texample: %prog [options] --url /path/to/build')

    # Args for describing the environment of the server machine
    group = optparse.OptionGroup(
        parser, 'Server Configuration', 'Options that specify the layout of '
        'the machine hosting this script.')
    group.add_option(
        '-g', '--gclient', default=DEFAULT_GCLIENT_ROOT,
        help=('Location of ChromeOS checkout. [default: %default]'))
    parser.add_option_group(group)

    # Args for configuring logging.
    group = mp_log_util.AddOptions(parser)
    group.add_option(
        '--log_path', default=DEFAULT_LOG_PATH,
        help=('Where to put individual host log files. [default: %default]'))
    group.add_option(
        '-n', '--no_log_files', default=False, action='store_true',
        help=('Skip writing output to files, instead display results on the '
              'console window only. [default: %default]'))
    group.add_option(
        '-e', '--echo_output', default=False, action='store_true',
        help=('Write command output to console. [default: %default]'))
    parser.add_option_group(group)

    # Args for selecting machines from Autotest
    group = autotest_util.AddOptions(parser)
    group.add_option(
        '-i', '--ip_addr',
        help=('IP address of single machine to run on.'))
    parser.add_option_group(group)

    # Args for defining how to run tasks from the server
    group = optparse.OptionGroup(
        parser, 'Execution Options', 'Options that define how commands are '
        'run on the remote machines.')
    group.add_option(
        '-p', '--parallel', type='int', default=DEFAULT_CONCURRENCY,
        help=('Number of hosts to be run concurrently. '
              '[default: %default].'))
    group.add_option(
        '-t', '--timeout', type='int', default=DEFAULT_TIMEOUT,
        help=('Time to wait before killing the attempt to run command. '
              '[default: %default]'))
    group.add_option(
        '--skip_ssh', default=False, action='store_true',
        help=('Skip SSH check before running on each device. '
              '[default: %default]'))
    group.add_option(
        '-l', '--lock', default=False, action='store_true',
        help='Lock device in Autotest while running. [default: %default]')
    parser.add_option_group(group)

    # Args for the action to take on each remote device
    group = optparse.OptionGroup(
        parser, 'Main Options', 'Options that define main action.  Selecting '
        'neither --script nor --url defaults to running a command on the '
        'hosts.')
    group.add_option(
        '-s', '--script', nargs=2,
        help=('Path to script to copy to host then execute.  2 args are '
              'required.  If the script does not take any args pass an empty '
              'string \" \"'))
    group.add_option(
        '--url',
        help=('Run image_to_live.sh with provided image URL. Note: Resets '
              'defaults for --lock=TRUE and --timeout=2400 and --parallel='
              '24.'))
    parser.add_option_group(group)

    options, args = parser.parse_args()

    options.cmd = None
    options.extra_args = None
    options.remote_file = None

    # If script/url was not specified, the remaining args are commands.
    if not options.script and not options.url:
      if not args:
        parser.error('Either script, command, or URL must be selected.')
      else:
        options.cmd, options.extra_args = args[0], ' '.join(args[1:])

    # Grab the arguments to the script and setup any extra args.
    if options.script:
      options.script, options.extra_args = options.script[0], options.script[1]
      options.remote_file = os.path.join(DEFAULT_REMOTE_COPY_PATH,
                                         options.script.split(os.path.sep)[-1])
    else:
      options.remote_file = ''

    # For updates reset default lock and timeout.
    if options.url:
      # Only modify these options if they still have their default values.  If
      # the user has already overwritten them keep the users values.
      if options.timeout == DEFAULT_TIMEOUT:
        options.timeout = DEFAULT_UPDATE_TIMEOUT
      if options.parallel == DEFAULT_CONCURRENCY:
        options.parallel = DEFAULT_UPDATE_CONCURRENCY

    # Create log folder if it doesn't exist.
    if not options.no_log_files and not os.path.exists(options.log_path):
      os.makedirs(options.log_path)

    return options


def ProcessResults(results, result_type):
  """Dump the results to the screen and/or log file.

  Args:
    results: Hosts with the same result type.
    result_type: String description of the result type.
  """
  msg = '%d hosts %s.\n' % (len(results), result_type)
  msg += ', '.join(results)
  mp_log_util.LogWithHeader(msg, width=80, symbol='-')


def main():
  """Run commands in parallel on remote hosts."""
  script_start_time = datetime.datetime.now()
  cm = CommandManager()
  if not cm.host_list:
    logging.error('No hosts found.')
    return
  logging.info('Found %d hosts.', len(cm.host_list))

  # Create work object for each host retrieved.
  hosts = [HostWorker(host, cm.options) for host in cm.host_list]

  # Submit work to pool.
  mp_tp = tp.MultiProcWorkPool(max_threads=cm.options.parallel)
  hosts = mp_tp.ExecuteWorkItems(
      hosts, provide_logger=True,
      logger_init_callback=mp_log_util.InitializeLogging, **vars(cm.options))

  # Now that work is done, output results.
  status_strings = {'PASS': 'succeeded',
                    'SSH': 'failed connecting via SSH',
                    'LOCK': 'failed locking in Autotest',
                    'COPY': 'failed copying script',
                    'CMD': 'failed executing command',
                    'URL': 'failed updating image'}
  results = {}
  for key in status_strings:
    results[key] = []

  # Divide results by result type for prettier reporting.
  for h in hosts:
    results[h.result].append(h.host)

  # Output final results.
  for result, hosts in results.items():
    if hosts:
      ProcessResults(hosts, status_strings[result])

  if not cm.options.no_log_files:
    logging.info('Log files located in %s', cm.options.log_path)

  # Follow up with some timing info.
  script_runtime = datetime.datetime.now() - script_start_time
  logging.info('Running Time = %d.%d seconds.',
               script_runtime.seconds, script_runtime.microseconds)


if __name__ == '__main__':
  main()
