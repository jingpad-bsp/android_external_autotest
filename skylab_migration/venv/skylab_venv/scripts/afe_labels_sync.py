#!/usr/bin/python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to sync CROS autotest afe_labels with Skylab inventory service.


This script is part of migration of autotest infrastructure services to skylab.
It is intended to run regularly in the autotest lab. It is mainly to sync
afe_replaced_labels, afe_static_labels, afe_static_hosts_labels tables with
inventory service. Below is a graph of the table relationship in the db:


            |afe_replaced_labels |                   |afe_static_hosts_labels
afe_labels  |  id                |afe_static_labels  |    id
id    ------|->label_id          |  id --------------|--> staticlabel_id
name  ------|--------------------|->name             |    host_id
            |                    |                   |


The workflow to sync these tables:
 - obtain the DUT information exposed by the skylab inventory service
 - When skylab is not alive:
   - Labels from inventory will be parsed into three namedtuples set, which
     represents database table:
     * AfeReplacedLabel(afe_label_name)
     * AfeStaticLabel(name, platform)
     * AfeStaticHostLabel(host_id, static_label_name)

     For a given label, if the host it attaches to does not exist in local
     afe_hosts table or the label itself does not have a corresponding entry
     in local afe_labels table (via name match), this label will be skipped.

   - Labels from local database will also be dumped into the same namedtuples.

   - Entries only exist in inventory namedtuple set will be inserted into the
     corresponding static table.
     Entries only exist in local db namedtuple set will be deleted from local
     db.
 - When skylab is alive
   - Labels from inentory will also be parsed into three namedtuples set
     as mentioned above.

     For a given label, if the host it attaches to does not exist in local
     afe_hosts table, it will be skipped.
     If the label itself does not have a corresponding entry in local
     afe_labels table (via name match), this label will be added to afe_labels
     first. If a new entry will be inserted into afe_static_hosts_labels, a
     corresponding entry mapping host to label in afe_labels will also be
     inserted into afe_hosts_labels table.

   - Labels from local database will also be dumped into the same namedtuples.

   - Three tables will be first inserted the entries only exist in inventory in
     the order: afe_static_hosts_labels, afe_static_labels, afe_replaced_labels
     - When delete from afe_static_labels, the correpsonding entry will also be
       removed from afe_labels.
     - When delete from afe_static_hosts_labels, the corresponding entry will
       also be removed from afe_hosts_labels table.
   - Then the three tables will delete the entries only exist in local db in
     the order: afe_static_labels, afe_static_hosts_labels, afe_replaced_labels
"""

import collections
import contextlib
import logging
import optparse
import signal
import sys
import time

from skylab_venv import sso_discovery

import common
import MySQLdb
from autotest_lib.client.common_lib import global_config

from chromite.lib import metrics
from chromite.lib import ts_mon_config


# Database connection variables.
DEFAULT_USER = global_config.global_config.get_config_value(
        'CROS', 'db_backup_user', type=str, default='')
DEFAULT_PASSWD = global_config.global_config.get_config_value(
        'CROS', 'db_backup_password', type=str, default='')
RESPEC_STATIC_LABELS = global_config.global_config.get_config_value(
    'SKYLAB', 'respect_static_labels', type=bool, default=False)
DB = 'chromeos_autotest_db'

AfeReplacedLabel = collections.namedtuple('AfeReplacedLabel',
                                          ['afe_label_name'])
AfeStaticLabel = collections.namedtuple('AfeStaticLabel', ['name', 'platform'])
AfeStaticHostLabel = collections.namedtuple('AfeStaticHostLabel',
                                            ['host_id', 'static_label_name'])

# Inventory parse constants
POOL_LABEL_PREFIX = 'DUT_POOL_'
VALID_EC = 'EC_TYPE_CHROME_OS'
PLATFORM_PREFIX = 'platform:'
EC_TYPE_MAP = {'EC_TYPE_CHROME_OS': 'cros'}

# Metrics
_METRICS_PREFIX = 'chromeos/autotest/skylab_migration/afe_labels'

# API
API_ROOT = 'https://inventory-dot-{project}.googleplex.com/_ah/api'
API = 'inventory_resources'
VERSION = 'v1'
DISCOVERY_URL = '%s/discovery/v1/apis/%s/%s/rest' % (API_ROOT, API, VERSION)
PROD_PROJECT = 'chromeos-skylab'
STAGING_PROJECT = 'chromeos-skylab-staging'
ENVIRONMENT_STAGING = 'ENVIRONMENT_STAGING'
ENVIRONMENT_PROD = 'ENVIRONMENT_PROD'

# Logging
INSERT_LOGS = ('Table {table} is not syncd up with inventory! Below is a list '
               'of entries only exist in inventory. These new entries will be '
               'inserted into local db:\n{entries}')
DELETE_LOGS = ('Table {table} is not syncd up with inventory! Below is a list '
               'of entries only exist in local db. Invalid entries will be '
               'deleted from local db:\n{entries}')

_shutdown = False
# A dict of hostname to host_id mapping in local afe_host table.
_hostname_id_map = {}
# A dict of label name to label_id mapping in local afe_labels table.
_labelname_id_map = {}


class SyncUpExpection(Exception):
  """Raised when failed to sync up server db."""
  pass


class UpdateDatabaseException(Exception):
  """Raised when failed to execute any database update mysql command."""
  pass


def get_hostname_to_id_map(cursor):
  """Dump the local afe_hosts table into a hostname to id dict.

  @param cursor: A mysql cursor object to the local database.

  @returns: a dict of hostname to host_id mappping.
  """
  cursor.execute('SELECT id, hostname FROM afe_hosts WHERE invalid=0')
  return {r[1]:r[0] for r in cursor.fetchall()}


def get_labelname_to_id_map(cursor):
  """Dump the local afe_labels table into a name to id dict.

  @param cursor: A mysql cursor object to the local database.

  @returns: a dict of label name to label_id mappping.
  """
  cursor.execute('SELECT id, name FROM afe_labels WHERE invalid=0')
  return {r[1]:r[0] for r in cursor.fetchall()}


def local_static_label_tables_dump(cursor):
  """Dump the static label related tables from local db into namedtuples.

  @param cursor: A mysql cursor object to the local database.

  @returns: a dict of table name to namedtuple mapping
  """
  cursor.execute('SELECT name FROM afe_replaced_labels t1 '
                 'JOIN afe_labels t2 ON t1.label_id = t2.id')
  afe_replaced_labels = map(AfeReplacedLabel._make, cursor.fetchall())

  cursor.execute('SELECT name, platform FROM afe_static_labels')
  afe_static_labels = map(AfeStaticLabel._make, cursor.fetchall())

  cursor.execute('SELECT host_id, name FROM afe_static_hosts_labels t1 '
                 'JOIN afe_static_labels t2 ON t1.staticlabel_id = t2.id')
  afe_static_hosts_labels = map(AfeStaticHostLabel._make, cursor.fetchall())

  return {'afe_replaced_labels': afe_replaced_labels,
          'afe_static_labels': afe_static_labels,
          'afe_static_hosts_labels': afe_static_hosts_labels}


def get_inventory_dut_labels(environment):
  """Get the dut labels info from inventory dut list API.

  @environment: the lab environment to sync the labels.

  @returns: A list of dict of dut infos. E.g.
          [{'hostname': 'a', 'labels':{'board':'x', 'platform':'x'}},
           {'hostname': 'b', 'labels':['board: 'y', 'platform':'y']}]
  """
  result = []
  if environment == ENVIRONMENT_PROD:
    api = API.format(project=PROD_PROJECT)
    discovery_url = DISCOVERY_URL.format(project=PROD_PROJECT)
  else:
    api = API.format(project=STAGING_PROJECT)
    discovery_url = DISCOVERY_URL.format(project=STAGING_PROJECT)

  # The page_size is tuned to be the maximum that won't cause call timeout
  service = sso_discovery.build_service(
      service_name=api, version=VERSION, discovery_service_url=discovery_url)
  page_token=''
  while True:
    response = service.labDevices().list(
        environment=environment, page_size=300, page_token=page_token).execute()
    page_token = response.get('next_page_token')
    result.extend(response.get('dut_infos', []))
    if not page_token:
     break

  return result


def parse_label_dict(label_dict):
  """Parse the label dict from inventory to a set of labels.

  Parse the label dict into a set of labels, which have the same format with
  the corresponding entry in the database. E.g
  {'board':'x', 'platform': 'x', 'capabilities':{'power':'battery'}} =>
  set('board:x', 'platform:x', 'power:battery')

  @param label_dict: the dict of labels get from inventory dut list API.

  @returns: the parsed set of labels.
  """
  labels_set = set()
  for key, value in label_dict.iteritems():
    # if value is empty, skip
    if not bool(value):
      continue
    if key in ['board', 'platform']:
      labels_set.add('%s:%s' % (key, value))
    elif key == 'capabilities':
      labels_set.update({'%s:%s' % (k, v) for k, v in value.iteritems() if v})
    elif key == 'critical_pools':
      for pool in value:
        pool = pool[len(POOL_LABEL_PREFIX):].replace('_', '-').lower()
        labels_set.add('pool:%s' % pool)
    elif key == 'ec':
      if value == VALID_EC:
        labels_set.add('ec:cros')
    elif key == 'self_serve_pools':
      labels_set.update({'pool:%s' % p for p in value})
    else:
      raise SyncUpExpection('Unknown static labels: %s:%s' % (key, value))

  return labels_set


def inventory_labels_parse(dut_infos, skylab_alive=False):
  """Parse the response from inventory API to namedtuples when sklab not alive

  When skylab is not alive, the source of truth is afe_labels table, so labels
  that do not exist in afe_labels will not be added to the static labels tables.

  When skylab is alive, the source of truth is inventory service, so labels that
  do not exist in the afe_labels will be added to both afe_static_labels and
  afe_labels table in update_afe_static_labels step.

  @param dut_infos: A list of dict of dut infos
  @param skylab_alive: whether skylab is alive or not

  @returns: a dict of table name to namedtuple mapping
  """
  afe_replaced_labels = set()
  afe_static_labels = set()
  afe_static_hosts_labels = set()
  for dut_info in dut_infos:
    hostname = dut_info['hostname']
    label_set = parse_label_dict(dut_info.get('labels', {}))
    # Host not exists in the local database, labels will not be added.
    if hostname not in _hostname_id_map.keys():
      logging.warning('Unknown host: %s only exists in inventory', hostname)
      continue

    # Host exists in the local database.
    host_id = _hostname_id_map[hostname]
    unknown_labels_to_afe_label_table = 0
    for label in label_set:
      # platform label will be removed the platform: prefix first.
      is_platform = label.startswith('platform')
      if is_platform:
        label = label[len(PLATFORM_PREFIX):]
      # Label not exists in afe_labels.
      if label not in _labelname_id_map.keys():
        if not skylab_alive:
          # Skylab not alive, unknown labels to afe_labels table cannot be added
          logging.info('Unknown label: %s only exists in inventory', label)
          unknown_labels_to_afe_label_table += 1
          continue

      afe_replaced_labels.add(
          AfeReplacedLabel(afe_label_name=label))
      afe_static_labels.add(
          AfeStaticLabel(name=label, platform=is_platform))
      afe_static_hosts_labels.add(
          AfeStaticHostLabel(host_id=host_id, static_label_name=label))

    if unknown_labels_to_afe_label_table > 0:
      metrics.Gauge(_METRICS_PREFIX + '/unknown_labels').set(
          unknown_labels_to_afe_label_table, fields={'host': hostname})
  return {'afe_replaced_labels': afe_replaced_labels,
          'afe_static_labels': afe_static_labels,
          'afe_static_hosts_labels': afe_static_hosts_labels}


def update_afe_static_labels(
    inventory_output, db_output, action, skylab_alive=False, *arg, **kwargs):
  """Create mysql commands to update afe_static_labels table.

  When skylab not alive, labels not exist in afe_labels will not be inserted.
  When deleting an entry from afe_static_labels table, the corresponding entry
  will not be deleted from afe_labels.

  When skylab is alive, labels not exist in afe_labels will be inserted into
  afe_labels too. When deleting an entry from afe_static_labels table, the
  corresponding entries will be deleted from afe_labels and afe_hosts_labels.

  @param inventory_output: a dict mapping table name to list of corresponding
                           namedtuples parsed from inventory.
  @param db_output: a dict mapping table name to list of corresponding
                    namedtuples parsed from local db.
  @param action: insert or delete.
  @param skylab_alive: Whether skylab is alive in prod or not.
  @param args: other positional arguments.
  @param kwargs: other keyword arguments.

  @returns a tuple of (table_name, action, list_of_cmds), e.g.
   ('afe_static_labels', 'insert, ['DELETE FROM afe_static_labels..])
  """
  table = 'afe_static_labels'
  logging.info('Checking table %s with inventory service...', table)
  cmds = []
  if action.lower() == 'insert':
    insert_entries = set(inventory_output[table]) - set(db_output[table])
    inconsistency_num = len(insert_entries)
    if insert_entries:
      logging.info(INSERT_LOGS.format(table=table, entries=insert_entries))

      for entry in insert_entries:
        label = entry.name.encode('utf-8')
        # When skylab is alive, labels will be also inserted into afe_labels
        cmds.append('INSERT INTO %s (name, platform, invalid, only_if_needed) '
                    'VALUES(%r, %d, 0, 0);' % (table, label, entry.platform))
        if skylab_alive:
          cmds.append('INSERT INTO afe_labels '
                      '(name, platform, invalid, only_if_needed) '
                      'VALUES(%r, %d, 0, 0);' % (label, entry.platform))
  elif action.lower() == 'delete':
    delete_entries = set(db_output[table]) - set(inventory_output[table])
    inconsistency_num = len(delete_entries)
    if delete_entries:
      logging.info(DELETE_LOGS.format(table=table, entries=delete_entries))

      for entry in delete_entries:
        label = entry.name.encode('utf-8')
        cmds.append('DELETE FROM %s WHERE name=%r;' % (table, label))
          # When skylab is alive, labels will be also removed from afe_labels
          # and all entries in afe_hosts_labels which attach to that label.
        if skylab_alive:
          cmds.append('DELETE FROM afe_hosts_labels WHERE label_id='
                      '(SELECT id FROM afe_labels WHERE name=%r);' % label)
          cmds.append('DELETE FROM afe_labels WHERE name=%r;' % label)
  else:
    raise SyncUpExpection(
        'Unknown mysql update action: %s, valid input: insert, delete')

  metrics.Gauge(_METRICS_PREFIX + 'inconsistency_found/%s' % table).set(
      inconsistency_num, fields={'action': 'to_%s' % action})
  return (table, action, cmds)


def update_afe_static_hosts_labels(
    inventory_output, db_output, action, skylab_alive=False, *args, **kwargs):
  """Create mysql commands to update afe_static_hosts_labels table.

  When skylab not alive, only insert or delete from afe_static_hosts_labels.

  When skylab is alive, inserting an entry into afe_static_hosts_labels will
  also insert corresponding entry in afe_hosts_labels table, which maps the
  label in afe_labels to that host. Deleting also deletes the matched one in
  afe_hosts_labels.

  @param inventory_output: a dict mapping table name to list of corresponding
                           namedtuples parsed from inventory.
  @param db_output: a dict mapping table name to list of corresponding
                    namedtuples parsed from local db.
  @param action: insert or delete.
  @param skylab_alive: whether skylab is alive or not.
  @param args: other positional arguments.
  @param kwargs: other keyword arguments.

  @returns a tuple of (table_name, action, list_of_cmds), e.g.
   ('afe_static_hosts_labels', 'insert, ['DELETE FROM afe_static_hosts_labels.])
  """
  table = 'afe_static_hosts_labels'
  logging.info('Checking table %s with inventory service...', table)
  cmds = []
  if action.lower() == 'insert':
    insert_entries = set(inventory_output[table]) - set(db_output[table])
    inconsistency_num = len(insert_entries)
    if insert_entries:
      logging.info(INSERT_LOGS.format(table=table, entries=insert_entries))

      for entry in insert_entries:
        label = entry.static_label_name.encode('utf-8')
        cmds.append('INSERT INTO %s (host_id, staticlabel_id) '
                    'SELECT %d, t.id FROM afe_static_labels t WHERE t.name=%r;'
                    % (table, entry.host_id, label))
        if skylab_alive:
          cmds.append('INSERT INTO afe_hosts_labels (host_id, label_id) '
                      'SELECT %d, t.id FROM afe_labels t WHERE t.name=%r;' %
                      (entry.host_id, label))
  elif action.lower() == 'delete':
    delete_entries = set(db_output[table]) - set(inventory_output[table])
    inconsistency_num = len(delete_entries)
    if delete_entries:
      logging.info(DELETE_LOGS.format(table=table, entries=delete_entries))

      for entry in delete_entries:
        label = entry.static_label_name.encode('utf-8')
        cmds.append('DELETE FROM %s WHERE host_id=%d AND staticlabel_id='
                    '(SELECT id FROM afe_static_labels WHERE name=%r);' %
                    (table, entry.host_id, label))
        if skylab_alive:
          cmds.append('DELETE FROM afe_hosts_labels WHERE host_id=%d AND '
                      'label_id=(SELECT id FROM afe_labels WHERE name=%r);' %
                      (entry.host_id, label))
  else:
    raise SyncUpExpection(
        'Unknown mysql update action: %s, valid input: insert, delete')

  metrics.Gauge(_METRICS_PREFIX + 'inconsistency_found/%s' % table).set(
      inconsistency_num, fields={'action': 'to_%s' % action})
  return (table, action, cmds)


def update_afe_replaced_labels(
    inventory_output, db_output, action, *args, **kwargs):
  """Create mysql commands to update afe_replaced_labels table.

  @param inventory_output: a dict mapping table name to list of corresponding
                           namedtuples parsed from inventory.
  @param db_output: a dict mapping table name to list of corresponding
                    namedtuples parsed from local db.
  @param action: insert or delete.
  @param args: other positional arguments.
  @param kwargs: other keyword arguments.

  @returns a tuple of (table_name, action, list_of_cmds), e.g.
   ('afe_replaced_labels', 'insert, ['DELETE FROM afe_replaced_labels..])
  """
  table = 'afe_replaced_labels'
  logging.info('Checking table %s with inventory service...', table)
  cmds = []
  if action.lower() == 'insert':
    insert_entries = set(inventory_output[table]) - set(db_output[table])
    inconsistency_num = len(insert_entries)
    if insert_entries:
      logging.info(INSERT_LOGS.format(table=table, entries=insert_entries))

      for entry in insert_entries:
        label = entry.afe_label_name.encode('utf-8')
        cmds.append('INSERT INTO %s (label_id) '
                    'SELECT id FROM afe_labels WHERE name=%r;' % (table, label))
  elif action.lower() == 'delete':
    delete_entries = set(db_output[table]) - set(inventory_output[table])
    inconsistency_num = len(delete_entries)
    if delete_entries:
      logging.info(DELETE_LOGS.format(table=table, entries=delete_entries))

      for entry in delete_entries:
        label = entry.afe_label_name.encode('utf-8')
        cmd = ('DELETE FROM %s WHERE label_id='
               '(SELECT id FROM afe_labels WHERE name=%r);' %
               (table, label))
        cmds.append(cmd)
  else:
    raise SyncUpExpection(
        'Unknown mysql update action: %s, valid input: insert, delete')

  metrics.Gauge(_METRICS_PREFIX + 'inconsistency_found/%s' % table).set(
      inconsistency_num, fields={'action': 'to_%s' % action})
  return (table, action, cmds)


def parse_options():
  """Parse the command line arguments."""
  usage = 'usage: %prog [options]'
  parser = optparse.OptionParser(usage=usage)
  parser.add_option('-o', '--host', default='localhost',
                    help='host of the Autotest DB. Default is localhost.')
  parser.add_option('-u', '--user', default=DEFAULT_USER,
                    help='User to login to the Autotest DB. Default is the '
                         'one defined in config file.')
  parser.add_option('-p', '--password', default=DEFAULT_PASSWD,
                    help='Password to login to the Autotest DB. Default is '
                         'the one defined in config file.')
  parser.add_option('-l', '--skylab_alive', action='store_true', default=False,
                    help='When skylab_alive is False, labels do not exist in '
                         'afe_labels will not be added to the db and to_be '
                         'delete labels will only be removed from static '
                         'tables. When True, new labels will be added both to '
                         'afe_labels and static tables. To-be-deleted labels '
                         'will be removed from both tables too.Default to '
                         'False')
  parser.add_option('-e', '--environment', default='prod',
                    help='Environment of the local database, prod or staging. '
                         'Default is prod')
  parser.add_option('-s', '--sleep', type=int, default=300,
                    help='Time to sleep between two server db sync. '
                         'Default is 300s')
  options, args = parser.parse_args()
  return parser, options, args


def verify_options_and_args(options, args):
  """Verify the validity of options and args.

  @param options: The parsed options to verify.
  @param args: The parsed args to verify.

  @returns: True if verification passes, False otherwise.
  """
  if args:
    logging.error('Unknown arguments: ' + str(args))
    return False

  if not (options.user and options.password):
    logging.error('Failed to get the default user of password for Autotest'
                  ' DB. Please specify them through the command line.')
    return False

  valid_env_inputs = ['prod', 'staging']
  if options.environment not in valid_env_inputs:
    logging.error('Invalid environment: %s, valid inputs: %s', valid_env_inputs)
    return False
  else:
    options.environment = 'ENVIRONMENT_%s' % options.environment.upper()

  return True


def _modify_table(cursor, mysql_cmds, table, action):
  """Helper method to commit a list of sql_cmds.

  @param cursor: mysql cursor instance.
  @param mysql_cmds: the list of sql cmd to be executed.
  @param table: the name of the table modified.
  @param action: Insert or delete action.
  """
  try:
    succeed = False
    for cmd in mysql_cmds:
      logging.info('Executing: %s', cmd)
      cursor.execute(cmd)
    succeed = True
  except Exception as e:
    msg = ('Fail to run the following sql command:\n%s\nError:\n%s\n'
           'All changes made to db will be rollback.' %
           (cmd, e))
    logging.error(msg)
    raise UpdateDatabaseException(msg)
  finally:
    metrics.Gauge(_METRICS_PREFIX + '/inconsistency_fixed').set(
        len(mysql_cmds),
        fields={'table': table, 'action': action, 'succeed': succeed})


@contextlib.contextmanager
def _msql_connection_with_transaction(options):
  """mysql connection helper.

  @param options: parsed command line options.
  """
  conn =  MySQLdb.connect(options.host, options.user, options.password, DB)
  try:
    yield conn
  except:
    conn.rollback()
    raise
  else:
    conn.commit()
  finally:
    conn.close()


@contextlib.contextmanager
def _cursor(conn):
  """mysql connect cursor helper.

  @param conn: a Mysql db connection instance.
  """
  cursor = conn.cursor()
  try:
    yield cursor
  finally:
    cursor.close()


def handle_signal(signum, frame):
  """Register signal handler."""
  global _shutdown
  _shutdown = True
  logging.info("Shutdown request received.")


def _main(options):
  """Main entry.

  @param args: parsed command line arguments.
  """
  global _hostname_id_map
  global _labelname_id_map

  dut_infos = get_inventory_dut_labels(environment=options.environment)
  with _msql_connection_with_transaction(options) as conn:
    with _cursor(conn) as cursor:
      _hostname_id_map = get_hostname_to_id_map(cursor)
      _labelname_id_map = get_labelname_to_id_map(cursor)
      inventory_output = inventory_labels_parse(dut_infos, options.skylab_alive)
      db_output = local_static_label_tables_dump(cursor)

      # Insert entries only exist in inventory. Insert order will be:
      # afe_static_labels -> afe_static_hosts_labels -> afe_replaced_labels
      for table in ['afe_static_labels',
                    'afe_static_hosts_labels',
                    'afe_replaced_labels']:
        update_func = globals()['update_%s' % table]
        table, action, cmds = update_func(
            inventory_output, db_output, 'insert', options.skylab_alive)
        _modify_table(cursor, cmds, table, action)

      # Delete entries only exist in local db. Delete order will be:
      # afe_static_hosts_labels -> afe_static_labels -> afe_replaced_labels
      for table in ['afe_static_hosts_labels',
                    'afe_static_labels',
                    'afe_replaced_labels']:
        update_func = globals()['update_%s' % table]
        table, action, cmds = update_func(
            inventory_output, db_output, 'delete', options.skylab_alive)
        _modify_table(cursor, cmds, table, action)

  logging.info('Successfully sync up static labels with inventory.')


def main(argv):
  """Entry point."""
  logging.basicConfig(level=logging.INFO,
                      format="%(asctime)s - %(name)s - " +
                      "%(levelname)s - %(message)s")
  parser, options, args = parse_options()
  if not verify_options_and_args(options, args):
    parser.print_help()
    sys.exit(1)

  with ts_mon_config.SetupTsMonGlobalState(service_name='sync_static_labels',
                                           indirect=True):
    try:
      metrics.Counter(_METRICS_PREFIX + '/start').increment()
      logging.info("Setting signal handler")
      signal.signal(signal.SIGINT, handle_signal)
      signal.signal(signal.SIGTERM, handle_signal)

      while not _shutdown:
        _main(options)
        metrics.Counter(_METRICS_PREFIX + '/tick').increment(
          fields={'success': True})
        time.sleep(options.sleep)
    except:
      metrics.Counter(_METRICS_PREFIX + '/tick').increment(
          fields={'success': False})
      raise


if __name__ == '__main__':
  main(sys.argv)
