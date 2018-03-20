#!/usr/bin/python
# Copyright (c) 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for afe_labels_sync."""

from __future__ import print_function

import mock
import unittest

from skylab_venv.scripts import afe_labels_sync as als

class AfeLabelSyncTest(unittest.TestCase):
  """Test server_db_sync."""

  INVENTORY_DUT_INFOS = [
      {
          "attributes": [],
          "environment": "ENVIRONMENT_STAGING",
          "hostname": "test_host1",
          "labels": {
              "board": "test_board1",
              "capabilities": {
                  "gpu_family": "",
                  "graphics": "",
                  "modem": "",
                  "power": "battery",
                  "telephony": ""},
              "critical_pools": [
                  "DUT_POOL_CTS_PERBUILD"],
              "ec": "EC_TYPE_CHROME_OS",
              "platform": "test_board1",
              "self_serve_pools": [
                  "test_serve_pool1",
                  "test_serve_pool2"]
          },
          "uuid": "test_uuid1"
      },
      {
          "attributes": [],
          "environment": "ENVIRONMENT_STAGING",
          "hostname": "test_host2",
          "labels": {
              "board": "test_board2",
              "capabilities": {
                  "gpu_family": "",
                  "graphics": "",
                  "modem": "",
                  "power": "battery",
                  "telephony": ""},
              "critical_pools": [
                  "DUT_POOL_BVT"],
              "ec": "EC_TYPE_INVALID",
              "platform": "test_board2",
              "self_serve_pools": ["test_serve_pool1"],
          },
          "uuid": "test_uuid2"
      },
  ]


  def testGetHostnameToIdMap(self):
    """Test get_hostname_to_id_map."""
    cursor_mock = mock.MagicMock()
    cursor_mock.fetchall.return_value= (
        (1, 'hostname_1'), (2, 'hostname_2'))
    expect_returns = {'hostname_1': 1, 'hostname_2': 2}

    results = als.get_hostname_to_id_map(cursor_mock)
    self.assertEqual(expect_returns, results)
    cursor_mock.execute.assert_called_once_with(
        'SELECT id, hostname FROM afe_hosts WHERE invalid=0')


  def testLabelNameToIdMap(self):
    """Test get_labelname_to_id_map."""
    cursor_mock = mock.MagicMock()
    cursor_mock.fetchall.return_value= (
        (1, 'test_label_1'), (2, 'test_label_2'))
    expect_returns = {'test_label_1': 1, 'test_label_2': 2}

    results = als.get_labelname_to_id_map(cursor_mock)
    self.assertEqual(expect_returns, results)
    cursor_mock.execute.assert_called_once_with(
        'SELECT id, name FROM afe_labels WHERE invalid=0')


  def testLocalStaticLabelTablesDump(self):
    """Test local_static_label_tables_dump."""
    cursor_mock = mock.MagicMock()
    cursor_mock.fetchall.side_effect = [
        (('test_label_1',),('test_label_2',),),
        (('test_label_1', 0,), ('test_label_2', 0,)),
        ((1, 'test_label_1',), (2, 'test_label_2',))
    ]

    expect_returns = {
        'afe_replaced_labels': [als.AfeReplacedLabel('test_label_1'),
                                als.AfeReplacedLabel('test_label_2')],
        'afe_static_labels': [als.AfeStaticLabel('test_label_1', 0),
                              als.AfeStaticLabel('test_label_2', 0)],
        'afe_static_hosts_labels': [als.AfeStaticHostLabel(1, 'test_label_1'),
                                    als.AfeStaticHostLabel(2, 'test_label_2')]
    }

    results = als.local_static_label_tables_dump(cursor_mock)
    self.assertEqual(expect_returns, results)
    calls = [mock.call('SELECT name FROM afe_replaced_labels t1 '
                       'JOIN afe_labels t2 ON t1.label_id = t2.id'),
             mock.call('SELECT name, platform FROM afe_static_labels'),
             mock.call('SELECT host_id, name FROM afe_static_hosts_labels t1 '
                       'JOIN afe_static_labels t2 '
                       'ON t1.staticlabel_id = t2.id')]
    cursor_mock.execute.assert_has_calls(calls)


  def testParseLabelDictWithEmptyValueForBoardAndPlatform(self):
    """Test whether to skip board or platform when its value is empty."""
    mock_label_dict = { 'board':'', 'platform':''}
    result = als.parse_label_dict(mock_label_dict)
    self.assertEqual(result, set())


  def testParseLabelDictWithEmptyValueForCapabilities(self):
    """Test whether to skip empty capabilities label."""
    mock_label_dict = {'capabilities': {'modem:':'', 'power':'test'}}
    result = als.parse_label_dict(mock_label_dict)
    self.assertEqual(result, set(['power:test']))


  def testParseLabelDictWithInvalidInputForEc(self):
    """Test whether to skip the invalid input for EC."""
    mock_label_dict = {'ec': 'EC_TYPE_INVALID'}
    result = als.parse_label_dict(mock_label_dict)
    self.assertEqual(result, set())


  def testParseLabelDictWithValidInput(self):
    """Test parse_label_dict."""
    result = als.parse_label_dict(
        self.INVENTORY_DUT_INFOS[0]['labels'])

    expect_labels_set = {
        'board:test_board1',
        'platform:test_board1',
        'power:battery',
        'pool:cts-perbuild',
        'ec:cros',
        'pool:test_serve_pool1',
        'pool:test_serve_pool2'
    }
    self.assertEqual(result, expect_labels_set)


  def testInventoryLabelParseWhenSkylabNotAliveWithUnknownHost(self):
    """Test inventory_labels_parse_when_skylab_not_alive with not exist host."""
    # Host in inventory service does not exist in local afe_hosts table.
    als._hostname_id_map = {'unknown_host': 0}
    als._labelname_id_map = {
        'board:test_board1': 1,
        'test_board1': 2,
        'power:battery': 3,
        'pool:cts-perbuild': 4,
        'ec:cros': 5,
        'pool:test_serve_pool1': 6,
        'pool:test_serve_pool2': 7}
    result = als.inventory_labels_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    for table in result.values():
      self.assertFalse(table)


  def testInventoryLabelParseWhenSkylabNotAliveWithUnknownHost(self):
    """Test inventory_labels_parse_when_skylab_not_alive with not exist host."""
    # Host in inventory service does not exist in local afe_hosts table.
    als._hostname_id_map = {'unknown_host': 0}
    als._labelname_id_map = {
        'board:test_board1': 1,
        'platform:test_board1': 2,
        'power:battery': 3,
        'pool:cts-perbuild': 4,
        'ec:cros': 5,
        'pool:test_serve_pool1': 6,
        'pool:test_serve_pool2': 7}
    result = als.inventory_labels_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    for table in result.values():
      self.assertFalse(table)


  def testInventoryLabelParseWhenSkylabNotAliveWithUnknownLabel(self):
    """Test inventory_labels_parse_when_skylab_not_alive with nonexist label."""
    als._hostname_id_map = {'test_host1': 1}
    # Only board:test_board1, platform:test_board1  exist in local afe_labels.
    als._labelname_id_map = {'board:test_board1': 1, 'test_board1': 2}
    result = als.inventory_labels_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    self.assertEquals(
        result['afe_replaced_labels'],
        {als.AfeReplacedLabel(afe_label_name='board:test_board1'),
         als.AfeReplacedLabel(afe_label_name='test_board1')})
    self.assertEqual(
        result['afe_static_labels'],
        {als.AfeStaticLabel(name='board:test_board1', platform=False),
         als.AfeStaticLabel(name='test_board1', platform=True)})
    self.assertEqual(
        result['afe_static_hosts_labels'],
        {als.AfeStaticHostLabel(host_id=1,
                                static_label_name='board:test_board1'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='test_board1')})


  def testInventoryLabelParseWhenSkylabAliveWithUnknownHost(self):
    """Test inventory_labels_parse_when_skylab_alive with not exist host."""
    # Host in inventory service does not exist in local afe_hosts table.
    als._hostname_id_map = {'unknown_host': 0}
    als._labelname_id_map = {
        'board:test_board1': 1,
        'platform:test_board1': 2,
        'power:battery': 3,
        'pool:cts-perbuild': 4,
        'ec:cros': 5,
        'pool:test_serve_pool1': 6,
        'pool:test_serve_pool2': 7}
    result = als.inventory_labels_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=True)
    for table in result.values():
      self.assertFalse(table)


  def testInventoryLabelParseWhenSkylabAliveWithUnknownLabel(self):
    """Test inventory_labels_parse_when_skylab_alive with nonexist label."""
    als._hostname_id_map = {'test_host1': 1}
    # Only board:test_board1, platform:test_board1  exist in local afe_labels.
    als._labelname_id_map = {'board:test_board1': 1, 'test_board1': 2}

    result = als.inventory_labels_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=True)
    self.assertEquals(
        result['afe_replaced_labels'],
        {als.AfeReplacedLabel(afe_label_name='board:test_board1'),
         als.AfeReplacedLabel(afe_label_name='test_board1'),
         als.AfeReplacedLabel(afe_label_name='power:battery'),
         als.AfeReplacedLabel(afe_label_name='pool:cts-perbuild'),
         als.AfeReplacedLabel(afe_label_name='ec:cros'),
         als.AfeReplacedLabel(afe_label_name='pool:test_serve_pool1'),
         als.AfeReplacedLabel(afe_label_name='pool:test_serve_pool2')})
    self.assertEqual(
        result['afe_static_labels'],
        {als.AfeStaticLabel(name='board:test_board1', platform=False),
         als.AfeStaticLabel(name='test_board1', platform=True),
         als.AfeStaticLabel(name='power:battery', platform=False),
         als.AfeStaticLabel(name='pool:cts-perbuild', platform=False),
         als.AfeStaticLabel(name='ec:cros', platform=False),
         als.AfeStaticLabel(name='pool:test_serve_pool1', platform=False),
         als.AfeStaticLabel(name='pool:test_serve_pool2', platform=False)})
    self.assertEqual(
        result['afe_static_hosts_labels'],
        {als.AfeStaticHostLabel(host_id=1,
                                static_label_name='board:test_board1'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='test_board1'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='power:battery'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='pool:cts-perbuild'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='ec:cros'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='pool:test_serve_pool1'),
         als.AfeStaticHostLabel(host_id=1,
                                static_label_name='pool:test_serve_pool2')})


  def testUpdateAfeStaticLabelsWithInvalidAction(self):
    """Test update_afe_static_labels with invalid action."""
    with self.assertRaises(als.SyncUpExpection):
      als.update_afe_static_labels({}, {}, 'invalid_action')


  def testUpdateAfeStaticLabelsWithInsertWhenSkylabNotAlive(self):
    """Test update_afe_static_labels with action insert when skylab not alive"""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be inserted.
    inventory_output = output_1
    db_output = output_2
    als._labelname_id_map = {}
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'insert', skylab_alive=False)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be inserted.
    inventory_output = output_2
    db_output = output_1
    als._labelname_id_map = {}
    expect_mysql_cmds = [
        "INSERT INTO afe_static_labels "
        "(name, platform, invalid, only_if_needed) "
        "VALUES('label:test', 0, 0, 0);"]
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'insert', skylab_alive=False)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticLabelsWithDeleteWhenSkylabNotAlive(self):
    """Test Update_afe_static_labels with delete when skylab not alive."""
    # When skylab is not alive, the static label will only be deleted from
    # afe_static_labels, not in afe_labels.
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be deleted
    inventory_output = output_2
    db_output = output_1
    als._labelname_id_map = {}
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'delete', skylab_alive=False)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be deleted.
    inventory_output = output_1
    db_output = output_2
    als._labelname_id_map = {'label:test': 1}
    expect_mysql_cmds = [
        "DELETE FROM afe_static_labels WHERE name='label:test';"]
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'delete', skylab_alive=False)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticLabelsWithInsertWhenSkylabAlive(self):
    """Test update_afe_static_labels with action insert when skylab alive"""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be inserted.
    inventory_output = output_1
    db_output = output_2
    als._labelname_id_map = {}
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'insert', skylab_alive=True)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be inserted.
    inventory_output = output_2
    db_output = output_1
    als._labelname_id_map = {}
    expect_mysql_cmds = [
        "INSERT INTO afe_static_labels "
        "(name, platform, invalid, only_if_needed) "
        "VALUES('label:test', 0, 0, 0);",
        "INSERT INTO afe_labels (name, platform, invalid, only_if_needed) "
        "VALUES('label:test', 0, 0, 0);"
    ]
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'insert', skylab_alive=True)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticLabelsWithDeleteWhenSkylabAlive(self):
    """Test update_afe_static_labels with delete when skylab alive."""
    # When skylab is alive, the static label will only be deleted from both
    # afe_static_labels, afe_labels, afe_hosts_labels table.
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {als.AfeReplacedLabel(
            afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be deleted
    inventory_output = output_2
    db_output = output_1
    als._labelname_id_map = {}
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'delete', skylab_alive=True)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be deleted.
    inventory_output = output_1
    db_output = output_2
    als._labelname_id_map = {'label:test': 1}
    expect_mysql_cmds = [
        "DELETE FROM afe_static_labels WHERE name='label:test';",
        "DELETE FROM afe_hosts_labels WHERE label_id=("
        "SELECT id FROM afe_labels WHERE name='label:test');",
        "DELETE FROM afe_labels WHERE name='label:test';"]
    _, _, mysql_cmds = als.update_afe_static_labels(
        inventory_output, db_output, 'delete', skylab_alive=True)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticHostsLabelsWithInvalidAction(self):
    """Test update_afe_static_hosts_labels with invalid action."""
    with self.assertRaises(als.SyncUpExpection):
      als.update_afe_static_hosts_labels({}, {}, 'invalid_action')


  def testUpdateAfeStaticHostsLabelsWithActionInsertWhenSkylabNotAlive(self):
    """Test update_afe_static_hosts_labels with insert when skylab not alive."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {als.AfeReplacedLabel(
            afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be inserted.
    inventory_output = output_1
    db_output = output_2
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'insert', skylab_alive=False)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be inserted.
    inventory_output = output_2
    db_output = output_1
    expect_mysql_cmds = [
        "INSERT INTO afe_static_hosts_labels (host_id, staticlabel_id) "
        "SELECT 1, t.id FROM afe_static_labels t WHERE t.name='label:test';"]
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'insert', skylab_alive=False)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticHostsLabelsWithActionDeleteWhenSkylabNotAlive(self):
    """Test update_afe_static_hosts_labels with delete when skylab not alive."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='afe_label_name')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be deleted.
    inventory_output = output_2
    db_output = output_1
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'delete', skylab_alive=False)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be deleted.
    inventory_output = output_1
    db_output = output_2
    expect_mysql_cmds = [
        "DELETE FROM afe_static_hosts_labels WHERE host_id=1 AND "
        "staticlabel_id=(SELECT id FROM afe_static_labels "
        "WHERE name='label:test');"]
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'delete', skylab_alive=False)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticHostsLabelsWithActionInsertWhenSkylabAlive(self):
    """Test update_afe_static_hosts_labels with insert when skylab alive."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {als.AfeReplacedLabel(
            afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be inserted.
    inventory_output = output_1
    db_output = output_2
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'insert', skylab_alive=True)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be inserted.
    inventory_output = output_2
    db_output = output_1
    expect_mysql_cmds = [
        "INSERT INTO afe_static_hosts_labels (host_id, staticlabel_id) "
        "SELECT 1, t.id FROM afe_static_labels t WHERE t.name='label:test';",
        "INSERT INTO afe_hosts_labels (host_id, label_id) "
        "SELECT 1, t.id FROM afe_labels t WHERE t.name='label:test';"]
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'insert', skylab_alive=True)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeStaticHostsLabelsWithActionDeleteWhenSkylabAlive(self):
    """Test update_afe_static_hosts_labels with delete when skylab not alive."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='afe_label_name')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be deleted.
    inventory_output = output_2
    db_output = output_1
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'delete', skylab_alive=True)
    self.assertFalse(mysql_cmds)

    # Test when find entry to be deleted.
    inventory_output = output_1
    db_output = output_2
    expect_mysql_cmds = [
        "DELETE FROM afe_static_hosts_labels WHERE host_id=1 AND "
        "staticlabel_id=(SELECT id FROM afe_static_labels "
        "WHERE name='label:test');",
        "DELETE FROM afe_hosts_labels WHERE host_id=1 AND "
        "label_id=(SELECT id FROM afe_labels WHERE name='label:test');"]
    _, _, mysql_cmds = als.update_afe_static_hosts_labels(
        inventory_output, db_output, 'delete', skylab_alive=True)
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeReplacedLabelsWithInvalidAction(self):
    """Test update_afe_replaced_labels with invalid action."""
    with self.assertRaises(als.SyncUpExpection):
      als.update_afe_replaced_labels({}, {}, 'invalid_action')


  def testUpdateAfeReplacedLabelsWithActionInsert(self):
    """Test update_afe_replaced_labels with action insert."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {
            als.AfeReplacedLabel(afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be inserted.
    inventory_output = output_1
    db_output = output_2
    _, _, mysql_cmds = als.update_afe_replaced_labels(
        inventory_output, db_output, 'insert')
    self.assertFalse(mysql_cmds)

    # Test when find entry to be inserted.
    inventory_output = output_2
    db_output = output_1
    expect_mysql_cmds = [
        "INSERT INTO afe_replaced_labels (label_id) "
        "SELECT id FROM afe_labels WHERE name='label:test';"]
    _, _, mysql_cmds = als.update_afe_replaced_labels(
        inventory_output, db_output, 'insert')
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


  def testUpdateAfeReplacedLabelsWithActionDelete(self):
    """Test update_afe_replaced_labels with action delete."""
    output_1 = {'afe_replaced_labels': set(), 'afe_static_labels': set(),
                'afe_static_hosts_labels': set()}
    output_2 = {
        'afe_replaced_labels': {als.AfeReplacedLabel(
            afe_label_name='label:test')},
        'afe_static_labels': {
            als.AfeStaticLabel(name='label:test', platform=False)},
        'afe_static_hosts_labels': {
            als.AfeStaticHostLabel(host_id=1, static_label_name='label:test')}}

    # Test when nothing to be deleted
    inventory_output = output_2
    db_output = output_1
    _, _, mysql_cmds = als.update_afe_replaced_labels(
        inventory_output, db_output, 'delete')
    self.assertFalse(mysql_cmds)

    # Test when find entry to be deleted.
    inventory_output = output_1
    db_output = output_2
    expect_mysql_cmds = [
        "DELETE FROM afe_replaced_labels WHERE label_id="
        "(SELECT id FROM afe_labels WHERE name='label:test');"]
    _, _, mysql_cmds = als.update_afe_replaced_labels(
        inventory_output, db_output, 'delete')
    self.assertEqual(mysql_cmds, expect_mysql_cmds)


if __name__ == '__main__':
  unittest.main()
