#!/usr/bin/env python2

# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Load generator for devserver.

Example usage:

# Find DUTs in suites pool to test with:
atest host list -b 'pool:suites,board:BOARD' --unlocked -s Ready

# Lock DUTs:
atest host mod -l -r 'quick provision testing' DUT1 DUT2

# Create config file with DUTs to test and builds to use.
cat >config.json <<EOD
{
  "BOARD": {
    "duts": [
      "chromeosX-rowY-rackZ-hostA",
      "chromeosX-rowY-rackZ-hostB",
    ],
    "versions": [
      "auron_paine-paladin/R65-10208.0.0-rc2",
      "auron_paine-paladin/R65-10208.0.0-rc3",
      "auron_paine-paladin/R65-10209.0.0-rc1"
    ]
  },
}
EOD

# Do 100 total provisions, aiming to have 10 active simultaneously.
loadtest.py $DS config.json --simultaneous 10 --total 100

# Unlock DUTs:
atest host mod -u DUT1 DUT2
"""

import collections
import datetime
import json
import random
import signal
import sys
import time

import common
from autotest_lib.client.common_lib import time_utils
from autotest_lib.client.common_lib.cros import dev_server
from chromite.lib import commandline
from chromite.lib import cros_logging as logging

# Paylods to stage.
PAYLOADS = ['quick_provision', 'stateful']

# Number of seconds between full status checks.
STATUS_POLL_SECONDS = 2

# Number of failures to blacklist a DUT.
BLACKLIST_TOTAL_FAILURE = 5
BLACKLIST_CONSECUTIVE_FAILURE = 2

def get_parser():
  """Creates the argparse parser."""
  parser = commandline.ArgumentParser(description=__doc__)
  parser.add_argument('server', type=str, action='store',
                      help='Devserver to load test.')
  parser.add_argument('config', type=str, action='store',
                      help='Path to JSON config file.'
                           'Config file is indexed by board with keys of '
                           '"duts" and "versions", each a list.')
  parser.add_argument('--boards', type=str, action='store',
                      help='Comma-separated list of boards to provision.')
  parser.add_argument('--dryrun', action='store_true', dest='dryrun',
                      help='Do not attempt to provision.')
  parser.add_argument('--outputlog', type=str, action='store',
                      help='Path to append JSON entries to.')
  parser.add_argument('--output', '-o', type=str, action='store',
                      help='Path to write JSON file to.')
  parser.add_argument('--simultaneous', type=int, action='store',
                      help='Number of simultaneous provisions to run.',
                      default=1)
  parser.add_argument('--no-stage', action='store_false',
                      dest='stage', default=True,
                      help='Do not attempt to stage builds.')
  parser.add_argument('--total', type=int, action='store',
                      help='Number of total provisions to run.',
                      default=0)
  return parser

def make_entry(entry_id, name, status, start_time,
               finish_time=None, parent=None, **kwargs):
  """Generate an event log entry to be stored in Cloud Datastore.

  @param entry_id: A (Kind, id) tuple representing the key.
  @param name: A string identifying the event
  @param status: A string identifying the status of the event.
  @param start_time: A datetime of the start of the event.
  @param finish_time: A datetime of the finish of the event.
  @param parent: A (Kind, id) tuple representing the parent key.

  @return A dictionary representing the entry suitable for dumping via JSON.
  """
  entry = {
      'id': entry_id,
      'name': name,
      'status': status,
      'start_time': time_utils.to_epoch_time(start_time),
  }
  if finish_time is not None:
    entry['finish_time'] = time_utils.to_epoch_time(finish_time)
  if parent is not None:
    entry['parent'] = parent
  return entry

class Job(object):
  """Tracks a single provision job."""
  def __init__(self, ds, host_name, build_name,
               entry_id=0, parent=None, board=None,
               start_active=0,
               force_update=False, full_update=False,
               clobber_stateful=True, quick_provision=True,
               dryrun=False):

    self.ds = ds
    self.host_name = host_name
    self.build_name = build_name

    self.entry_id = ('Job', entry_id)
    self.parent = parent
    self.board = board
    self.start_active = start_active
    self.end_active = None
    self.check_active_sum = 0
    self.check_active_count = 0

    self.start_time = datetime.datetime.now()
    self.finish_time = None

    self.kwargs = {
        'host_name': host_name,
        'build_name': build_name,
        'force_update': force_update,
        'full_update': full_update,
        'clobber_stateful': clobber_stateful,
        'quick_provision': quick_provision,
    }

    if dryrun:
      self.finish_time = datetime.datetime.now()
      self.raised_error = None
      self.success = True
      self.pid = 0
    else:
      self.trigger_response = ds._trigger_auto_update(**self.kwargs)

  def as_entry(self):
    """Generate an entry for exporting to datastore."""
    entry = make_entry(self.entry_id, self.host_name,
                       'pass' if self.success else 'fail',
                       self.start_time, self.finish_time, self.parent)
    entry.update({
        'build_name': self.build_name,
        'board': self.board,
        'devserver': self.ds.hostname,
        'start_active': self.start_active,
        'end_active': self.end_active,
        'force_update': self.kwargs['force_update'],
        'full_update': self.kwargs['full_update'],
        'clobber_stateful': self.kwargs['clobber_stateful'],
        'quick_provision': self.kwargs['quick_provision'],
        'elapsed': int(self.elapsed().total_seconds()),
    })
    if self.check_active_count:
      entry['avg_active'] = self.check_active_sum / self.check_active_count
    return entry

  def check(self, active_count):
    """Checks if a job has completed.

    @param active_count: Number of active provisions at time of the check.
    @return: True if the job has completed, False otherwise.
    """
    if self.finish_time is not None:
      return True

    self.check_active_sum += active_count
    self.check_active_count += 1

    finished, raised_error, pid = self.ds.check_for_auto_update_finished(
        self.trigger_response, wait=False, **self.kwargs)
    if finished:
      self.finish_time = datetime.datetime.now()
      self.raised_error = raised_error
      self.success = self.raised_error is None
      self.pid = pid
      self.end_active = active_count

    return finished

  def elapsed(self):
    """Determine the elapsed time of the task."""
    finish_time = self.finish_time or datetime.datetime.now()
    return finish_time - self.start_time

class Runner(object):
  """Parallel provision load test runner."""
  def __init__(self, ds, duts, config, simultaneous=1, total=0,
               outputlog=None, dryrun=False):
    self.ds = ds
    self.duts = duts
    self.config = config
    self.start_time = datetime.datetime.now()
    self.finish_time = None
    self.simultaneous = simultaneous
    self.total = total
    self.outputlog = outputlog
    self.dryrun = dryrun

    self.active = []
    self.started = 0
    self.completed = []
    # Track DUTs which have failed multiple times.
    self.dut_blacklist = set()
    # Track versions of each DUT to provision in order.
    self.last_versions = {}

    # id for the parent entry.
    # TODO: This isn't the most unique.
    self.entry_id = ('Runner',
                     int(time_utils.to_epoch_time(datetime.datetime.now())))

    # ids for the job entries.
    self.next_id = 0

    if self.outputlog:
      dump_entries_as_json([self.as_entry()], self.outputlog)

  def signal_handler(self, signum, frame):
    """Signal handle to dump current status."""
    logging.info('Received signal %s', signum)
    if signum == signal.SIGUSR1:
      now = datetime.datetime.now()
      logging.info('%d active provisions, %d completed provisions, %s elapsed:',
                   len(self.active), len(self.completed), now - self.start_time)
      for job in self.active:
        logging.info('  %s -> %s, %s elapsed',
                     job.host_name, job.build_name, now - job.start_time)

  def as_entry(self):
    """Generate an entry for exporting to datastore."""
    entry = make_entry(self.entry_id, 'Runner', 'pass',
                       self.start_time, self.finish_time)
    entry.update({
        'devserver': self.ds.hostname,
    })
    return entry

  def get_completed_entries(self):
    """Retrieves all completed jobs as entries for datastore."""
    entries = [self.as_entry()]
    entries.extend([job.as_entry() for job in self.completed])
    return entries

  def get_next_id(self):
    """Get the next Job id."""
    entry_id = self.next_id
    self.next_id += 1
    return entry_id

  def spawn(self, host_name, build_name):
    """Spawn a single provision job."""
    job = Job(self.ds, host_name, build_name,
              entry_id=self.get_next_id(), parent=self.entry_id,
              board=self.get_dut_board_type(host_name),
              start_active=len(self.active), dryrun=self.dryrun)
    self.active.append(job)
    logging.info('Provision of %s to %s started', job.host_name, job.build_name)
    self.last_versions[host_name] = build_name
    self.started += 1

  def replenish(self):
    """Replenish the number of active provisions to match goals."""
    while (len(self.active) < self.simultaneous and
           (self.total == 0 or self.started < self.total)):
      host_name = self.find_idle_dut()
      if host_name:
        build_name = self.find_build_for_dut(host_name)
        self.spawn(host_name, build_name)
      else:
        logging.warn('Insufficient DUTs to satisfy goal')
        return False
    return True

  def check_all(self):
    """Check the status of outstanding provisions."""
    still_active = []
    for job in self.active:
      if job.check(len(self.active)):
        logging.info('Provision of %s to %s %s in %s: %s',
                     job.host_name, job.build_name,
                     'completed' if job.success else 'failed',
                     job.elapsed(), job.raised_error)
        entry = job.as_entry()
        logging.debug(json.dumps(entry))
        if self.outputlog:
          dump_entries_as_json([entry], self.outputlog)
        self.completed.append(job)
        if self.should_blacklist(job.host_name):
          logging.error('Blacklisting DUT %s', job.host_name)
          self.dut_blacklist.add(job.host_name)
      else:
        still_active.append(job)
    self.active = still_active

  def should_blacklist(self, host_name):
    """Determines if a given DUT should be blacklisted."""
    jobs = [job for job in self.completed if job.host_name == host_name]
    total = 0
    consecutive = 0
    for job in jobs:
      if not job.success:
        total += 1
        consecutive += 1
        if ((BLACKLIST_TOTAL_FAILURE is not None and
             total >= BLACKLIST_TOTAL_FAILURE) or
            (BLACKLIST_CONSECUTIVE_FAILURE is not None and
             consecutive >= BLACKLIST_CONSECUTIVE_FAILURE)):
          return True
      else:
        consecutive = 0
    return False

  def find_idle_dut(self):
    """Find an idle DUT to provision.."""
    active_duts = {job.host_name for job in self.active}
    idle_duts = [d for d in self.duts
                 if d not in active_duts | self.dut_blacklist]
    return random.choice(idle_duts) if len(idle_duts) else None

  def get_dut_board_type(self, host_name):
    """Determine the board type of a DUT."""
    return self.duts[host_name]

  def get_board_versions(self, board):
    """Determine the versions to provision for a board."""
    return self.config[board]['versions']

  def find_build_for_dut(self, host_name):
    """Determine a build to provision on a DUT."""
    board = self.get_dut_board_type(host_name)
    versions = self.get_board_versions(board)
    last_version = self.last_versions.get(host_name)
    try:
      last_index = versions.index(last_version)
    except ValueError:
      return versions[0]
    return versions[(last_index + 1) % len(versions)]

  def stage_all(self):
    """Stage all necessary artifacts."""
    boards = set(self.duts.values())
    logging.info('Staging for %d boards', len(boards))
    for board in boards:
      for build in self.get_board_versions(board):
        logging.debug('Staging %s', build)
        self.ds.stage_artifacts(build, PAYLOADS)

  def loop(self):
    """Run the main provision loop."""
    # Install a signal handler for status updates.
    old_handler = signal.signal(signal.SIGUSR1, self.signal_handler)
    signal.siginterrupt(signal.SIGUSR1, False)

    try:
      while True:
        self.check_all()
        if self.total != 0 and len(self.completed) >= self.total:
          break
        if not self.replenish() and len(self.active) == 0:
          logging.error('Unable to replenish with no active provisions')
          return False
        logging.debug('%d provisions active', len(self.active))
        time.sleep(STATUS_POLL_SECONDS)
      return True
    except KeyboardInterrupt:
      return False
    finally:
      self.finish_time = datetime.datetime.now()
      # Clean up signal handler.
      signal.signal(signal.SIGUSR1, old_handler)

  def elapsed(self):
    """Determine the elapsed time of the task."""
    finish_time = self.finish_time or datetime.datetime.now()
    return finish_time - self.start_time

def dump_entries_as_json(entries, output_file):
  """Dump event log entries as json to a file.

  @param entries: A list of event log entries to dump.
  @param output_file: The file to write to.
  """
  # Write the entries out as JSON.
  logging.debug('Dumping %d entries' % len(entries))
  for e in entries:
    json.dump(e, output_file, sort_keys=True)
    output_file.write('\n')
    output_file.flush()

def main(argv):
  """Load generator for a devserver."""
  parser = get_parser()
  options = parser.parse_args(argv)

  if options.server:
    server = 'http://%s/' % options.server
    ds = dev_server.ImageServer(server)
  else:
    parser.print_usage()
    logging.error('Must specify --server')
    sys.exit(1)

  # Parse config file and determine master list of duts and their board type,
  # filtering by board type if specified.
  duts = {}
  if options.config:
    with open(options.config, 'r') as f:
      config = json.load(f)
      boards = options.boards.split(',') if options.boards else config.keys()
      for board in boards:
        duts.update({dut: board for dut in config[board]['duts']})
    logging.info('Config file %s: %d boards, %d duts',
                 options.config, len(boards), len(duts))
  else:
    parser.print_usage()
    logging.error('Must specify --config')
    sys.exit(1)

  # Set up the test runner and stage all the builds.
  outputlog = open(options.outputlog, 'a') if options.outputlog else None
  runner = Runner(ds, duts, config,
                  simultaneous=options.simultaneous, total=options.total,
                  outputlog=outputlog,
                  dryrun=options.dryrun)
  if options.stage:
    runner.stage_all()

  # Run all the provisions.
  completed = runner.loop()
  logging.info('%s in %s', 'Completed' if completed else 'Interrupted',
               runner.elapsed())
  # Write all entries as JSON.
  entries = runner.get_completed_entries()
  if options.output:
    with open(options.output, 'w') as f:
      dump_entries_as_json(entries, f)
  else:
    dump_entries_as_json(entries, sys.stdout)
  logging.info('Summary: %s',
               dict(collections.Counter([e['status'] for e in entries
                                         if e['name'] != 'Runner'])))

  # List blacklisted DUTs.
  if runner.dut_blacklist:
    logging.warn('Blacklisted DUTs:')
    for host_name in runner.dut_blacklist:
      logging.warn('  %s', host_name)

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
