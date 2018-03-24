#!/usr/bin/python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to sync CROS autotest static attributes with Skylab inventory service.

This script is part of migration of autotest infrastructure services to skylab.
It is intended to run regularly in the autotest lab to sync
afe_static_host_attributes with inventory service.

This workflow to sync static attributes with inventory:
  - obtain the DUT information exposed by the skylab inventory service
  - When skylab is not alive:
    - Attributes from inventory will be parsed into a namedtuple set, which
      represents afe_static_host_attributes table.
      * AfeStaticHostAttr(host_id, attribute, value)

    For a given attribute, if the host it attaches to does not exist in local
    afe_hosts table or the host&attribute pair does not exist in
    afe_host_attributes pair or the host&attribute&value is not same with that
    in afe_host_attributes table, the attribute will be skipped.

  - Attributes from local afe_static_host_attributes table will also be dumped
    into the same namedtuple set.

   - Entries only exist in inventory namedtuple set will be inserted into the
     corresponding static table.
     Entries only exist in local db namedtuple set will be deleted from local
     db.
 - When skylab is alive
   - Attributes from inventory will also be parsed into the namedtuples set
     as mentioned above.

   - Labels from local database will also be dumped into the same namedtuples.

   - For a given attribute to be inserted into afe_static_host_attributes,
    if the host it attaches to does not exist in local
    afe_hosts table, it will be skipped. If the host&attribute pair does not
    exist in afe_host_attributes, it will be inserted into both
    afe_host_attributes and afe_static_host_attributes. If the
    host&attribute&value is not same with that in afe_host_attributes table, it
    will be inserted into afe_host_attributes, and the entry in
    afe_host_attributes table will be updated.
  - For a given attribute to be deleted from afe_static_host_attributes, it
    will be removed from both tables.
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
DB = 'chromeos_autotest_db'

AfeStaticHostAttr = collections.namedtuple('AfeStaticHostAttr',
                                           ['host_id', 'attribute', 'value'])

# Metrics
_METRICS_PREFIX = 'chromeos/autotest/skylab_migration/afe_attributes'

# API
API_ROOT = 'https://inventory-dot-{project}.googleplex.com/_ah/api'
API = 'inventory_resources'
VERSION = 'v1'
DISCOVERY_URL = '%s/discovery/v1/apis/%s/%s/rest' % (API_ROOT, API, VERSION)
PROD_PROJECT = 'chromeos-skylab'
STAGING_PROJECT = 'chromeos-skylab-staging'
ENVIRONMENT_STAGING = 'ENVIRONMENT_STAGING'
ENVIRONMENT_PROD = 'ENVIRONMENT_PROD'

_shutdown = False
# A dict of hostname to host_id mapping in local afe_host table.
_hostname_id_map = {}
# A dict of (host_id, attribute) to value mapping in local afe_host_attributes.
_hostattr_value_map = {}


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


def get_host_attr_to_value_map(cursor):
  """Dump afe_host_attributes table into (host_id, attribute) to value map.

  @param cursor: A mysql cursor object to the local database.

  @returns: a dict of (host_id, attribute) to value mappping.
  """
  cursor.execute('SELECT host_id, attribute, value FROM afe_host_attributes;')
  return {(r[0], r[1]): r[2] for r in cursor.fetchall()}


def local_static_host_attribute_table_dump(cursor):
  """Dump afe_static_host_attributes from local db into namedtuples.

  @param cursor: A mysql cursor object to the local database.

  @returns: AfeStaticHostAttr namedtuple.
  """
  cursor.execute('SELECT host_id, attribute, value '
                 'FROM afe_static_host_attributes;')
  afe_static_host_attrs = map(AfeStaticHostAttr._make, cursor.fetchall())

  return afe_static_host_attrs


def get_inventory_dut_attributes(environment):
  """Get the dut attributes info from inventory dut list API.

  @environment: the lab environment to sync the labels.

  @returns: A list of dict of dut infos. E.g.
          [{'hostname': 'a', 'attributes':['HWID=x', 'serial_number=x'}},
           {'hostname': 'b', 'attributes':['HWID=y', 'serial_number=y']}]
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


def inventory_attrs_parse(dut_infos, skylab_alive=False):
  """Parse the response from inventory API to AfeStaticHostAttr namedtuple.

  When skylab is not alive, the source of truth is afe_host_attributes table,
  so attributes that do not exist in afe_host_attributes table will not be
  added to afe_static_host_attributes table.

  When skylab is alive, the source of truth is inventory service, attributes
  that do not exist in the afe_host_attributes table will be added to
  afe_host_attributes table first.

  @param dut_infos: A list of dict of dut infos
  @param skylab_alive: whether skylab is alive or not

  @returns: AfeStaticHostAttr namedtuple.
  """
  afe_static_host_attrs = set()
  for dut_info in dut_infos:
    hostname = dut_info['hostname']
    # Host not exists in the local database, attributes will not be added.
    if hostname not in _hostname_id_map.keys():
      logging.warning('Unknown host: %s only exists in inventory', hostname)
      continue

    # Host exists in the local database. Parse attributes from
    # ['a=b', 'c=d', 'e'] to set(('a', 'b'), ('c', 'd')), skip empty values.
    host_id = _hostname_id_map[hostname]
    attr_list = [tuple(a.split('=')) for a in dut_info.get('attributes', [])]
    attr_set = set(filter(lambda x: bool(x[1]), attr_list))

    unknown_attrs_to_afe_host_attributes_table = 0
    for attr, value in attr_set:
      # Attribute not exists in afe_host_attributes or the value from inventory
      # does not match that in afe_host_attributes.
      if ((host_id, attr) not in _hostattr_value_map.keys() or
          _hostattr_value_map.get((host_id, attr)) != value):
        if not skylab_alive:
          # Skylab not alive, unknown attributes to afe_host_attribute table
          # cannot be added.
          logging.info('Unknown host attribute: %s, %s=%s only exists in '
                       'inventory', hostname, attr, value)
          unknown_attrs_to_afe_host_attributes_table += 1
          continue

      afe_static_host_attrs.add(AfeStaticHostAttr(
          host_id=host_id, attribute=attr, value=value))

    if unknown_attrs_to_afe_host_attributes_table > 0:
      metrics.Gauge(_METRICS_PREFIX + '/unknown_attributes').set(
          unknown_attrs_to_afe_host_attributes_table, fields={'host': hostname})
  return afe_static_host_attrs


def update_afe_static_host_attributes(
    inventory_output, db_output, skylab_alive=False):
  """Create mysql commands to update afe_static_host_attributes table.

  When skylab not alive, attributes not exist in afe_host_attributes table or
  the value from inventory does not match that in afe_host_attributes table
  will not be inserted into afe_static_host_attributes table. When deleting an
  entry from afe_static_host_attributes, the corresponding entry will not be
  deleted from afe_host_attributes table.

  When skylab is alive, attributes not exist in afe_host_attributes table will
  be inserted into it. Attribute whose value differs between inventory and
  afe_host_attributes will be updated in afe_host_attributes. When deleting an
  entry from afe_static_host_attributes, the corresponding entry will be deleted
  from afe_host_attributes table too.

  @param inventory_output: a dict mapping table name to list of corresponding
                           namedtuples parsed from inventory.
  @param db_output: a dict mapping table name to list of corresponding
                    namedtuples parsed from local db.
  @param skylab_alive: Whether skylab is alive in prod or not.

  @returns: A list of mysql update commands, e.g.
  ['INSERT INTO afe_static_host_attributes ...']
  """
  table = 'afe_static_host_attributes'
  logging.info('Checking %s with inventory...', table)
  mysql_cmds = []

  delete_entries = set(db_output) - set(inventory_output)
  insert_entries = set(inventory_output) - set(db_output)

  if delete_entries:
    logging.info('\nTable %s is not synced up! Below is a list of entries '
                 'that exist only in local db. These invalid entries will be '
                 'deleted from local db:\n%s',  table, delete_entries)
    for entry in delete_entries:
      attr = entry.attribute.encode('utf-8')
      value = entry.value.encode('utf-8')
      mysql_cmds.append('DELETE FROM %s WHERE host_id=%d AND attribute=%r '
                        'AND value=%r;' % (table, entry.host_id, attr, value))
      if skylab_alive:
        mysql_cmds.append('DELETE FROM afe_host_attributes WHERE '
                          'host_id=%d AND attribute=%r AND value=%r;' %
                          (entry.host_id, attr, value))
        _hostattr_value_map.pop((entry.host_id, attr))

  if insert_entries:
    logging.info('\nTable %s is not synced up! Below is a list of entries '
                 'that exist only in inventory service. These new entries will'
                 ' be inserted in to local db:\n%s', table, insert_entries)
    for entry in insert_entries:
      attr = entry.attribute.encode('utf-8')
      value = entry.value.encode('utf-8')
      mysql_cmds.append('INSERT INTO %s (host_id, attribute, value) '
                        'VALUES(%d, %r, %r);' %
                        (table, entry.host_id, attr, value))
      if skylab_alive:
        # attibute not exist in afe_host_attributes, insert it.
        if not _hostattr_value_map.get((entry.host_id, attr)):
          mysql_cmds.append('INSERT INTO afe_host_attributes '
                            '(host_id, attribute, value) VALUES(%d, %r, %r);' %
                            (entry.host_id, attr, value))
        # attribute exists in afe_host_attributes, but value differs.
        elif _hostattr_value_map.get((entry.host_id, attr)) != value:
          mysql_cmds.append('UPDATE afe_host_attributes SET value=%r '
                            'WHERE host_id=%d AND attribute=%r;' %
                            (value, entry.host_id, attr))

  metrics.Gauge(_METRICS_PREFIX + '/inconsistency_found').set(
      len(delete_entries), fields={'table': table, 'action': 'to_delete'})
  metrics.Gauge(_METRICS_PREFIX + '/inconsistency_found').set(
      len(insert_entries), fields={'table': table, 'action': 'to_add'})

  return mysql_cmds


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
                    help='When skylab_alive is False, attributes not exist in '
                         'afe_host_attributes will not be added to db and to_be'
                         ' delete attributes will only be removed from static '
                         'tables. When True, new attributes will be added both '
                         'to afe_host_attributes and static table. '
                         'To-be-deleted labels will be removed from both '
                         'tables too. Default to False')
  parser.add_option('-e', '--environment', default='prod',
                    help='Environment of the server_db, prod or staging. '
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


def _modify_table(cursor, mysql_cmds, table):
  """Helper method to commit a list of sql_cmds.

  @param cursor: mysql cursor instance.
  @param mysql_cmds: the list of sql cmd to be executed.
  @param table: the name of the table modified.
  """
  try:
    succeed = False
    for cmd in mysql_cmds:
      logging.info('Executing: %s', cmd)
      cursor.execute(cmd)
    succeed = True
  except Exception as e:
    msg = ('Fail to run the following sql command:\n%s\nError:\n%s\n'
           'All changes made to server db will be rollback.' %
           (cmd, e))
    logging.error(msg)
    raise UpdateDatabaseException(msg)
  finally:
    num_deletes = len([cmd for cmd in mysql_cmds if cmd.startswith('DELETE')])
    num_inserts = len([cmd for cmd in mysql_cmds if cmd.startswith('INSERT')])
    metrics.Gauge(_METRICS_PREFIX + '/inconsistency_fixed').set(
        num_deletes,
        fields={'table': table, 'action': 'delete', 'succeed': succeed})
    metrics.Gauge(_METRICS_PREFIX + '/inconsistency_fixed').set(
        num_inserts,
        fields={'table': table, 'action': 'insert', 'succeed': succeed})


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
  global _hostattr_value_map

  dut_infos = get_inventory_dut_attributes(environment=options.environment)
  with _msql_connection_with_transaction(options) as conn:
    with _cursor(conn) as cursor:
      _hostname_id_map = get_hostname_to_id_map(cursor)
      _hostattr_value_map = get_host_attr_to_value_map(cursor)
      inventory_static_attrs = inventory_attrs_parse(dut_infos,
                                                     options.skylab_alive)
      db_static_attrs = local_static_host_attribute_table_dump(cursor)

      mysql_cmds = update_afe_static_host_attributes(
          inventory_static_attrs, db_static_attrs, options.skylab_alive)
      _modify_table(cursor, mysql_cmds, 'afe_static_host_attributes')
      logging.info('Successfully synced table afe_static_host_attributes with '
                   'inventory service.')


def main(argv):
  """Entry point."""
  logging.basicConfig(level=logging.INFO,
                      format="%(asctime)s - %(name)s - " +
                      "%(levelname)s - %(message)s")
  parser, options, args = parse_options()
  if not verify_options_and_args(options, args):
    parser.print_help()
    sys.exit(1)

  with ts_mon_config.SetupTsMonGlobalState(service_name='afe_attrs_sync',
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

