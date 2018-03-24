#!/usr/bin/python
# Copyright (c) 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for afe_attrs_sync."""

from __future__ import print_function

import mock
import unittest

from skylab_venv.scripts import afe_attrs_sync as ats

class AfeAttrsSyncTest(unittest.TestCase):
  """Test afe_attrs_sync."""

  INVENTORY_DUT_INFOS = [
      {
          "hostname": "test_host1",
          "attributes": [
               "HWID=test_hwid_1",
               "serial_number=test_serial_num_1",
          ]
      },
      {
          "hostname": "test_host2",
          "attributes": [
               "HWID=test_hwid_2",
               "serial_number=test_serial_num_2",
               "powerunit_hostname=",
               "powerunit_outlet="
          ]
      }
  ]


  def testGetHostnameToIdMap(self):
    """Test get_hostname_to_id_map."""
    cursor_mock = mock.MagicMock()
    cursor_mock.fetchall.return_value= (
        (1, 'hostname_1'), (2, 'hostname_2'))
    expect_returns = {'hostname_1': 1, 'hostname_2': 2}

    results = ats.get_hostname_to_id_map(cursor_mock)
    self.assertEqual(expect_returns, results)
    cursor_mock.execute.assert_called_once_with(
        'SELECT id, hostname FROM afe_hosts WHERE invalid=0')


  def testGetHostAttrToValueMap(self):
    """Test get_host_attr_to_value_map."""
    cursor_mock = mock.MagicMock()
    cursor_mock.fetchall.return_value= (
        (1, 'test_attr_1', 'test_value_1'),
        (2, 'test_attr_2', 'test_value_2'))
    expect_returns = {(1, 'test_attr_1'): 'test_value_1',
                      (2, 'test_attr_2'): 'test_value_2'}

    results = ats.get_host_attr_to_value_map(cursor_mock)
    self.assertEqual(expect_returns, results)
    cursor_mock.execute.assert_called_once_with(
        'SELECT host_id, attribute, value FROM afe_host_attributes;')


    def testLocalStaticHostAttributeTableDump(self):
      """Test local_static_host_attribute_table_dump."""
      cursor_mock = mock.MagicMock()
      cursor_mock.fetchall.return_value = (
        (1, 'test_attr_1', 'test_value_1'),
        (2, 'test_attr_2', 'test_value_2'))

      expect_return = set(
          ats.AfeStaticHostAttr(host_id=1,
                                attribute='test_attr_1',
                                value='test_value_1'),
          ats.AfeStaticHostAttr(host_id=2,
                                attribute='test_attr_2',
                                value='test_value_2')
      )

      result = ats.local_static_host_attribute_table_dump(cursor_mock)
      self.assertEqual(expect_return, result)
      cursor_mock.execute.assert_called_once_with(
          'SELECT host_id, attribute, value '
          'FROM afe_static_host_attributes;'
      )


  def testInventoryAttrsParseWhenSkylabNotAliveWithUnknownHost(self):
    """Test inventory_attrs_parse when skylab not alive with not exist host."""
    # Host in inventory service does not exist in afe_hosts table.""
    ats._hostname_id_map = {}
    ats._hostattr_value_map = {}

    result = ats.inventory_attrs_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    self.assertFalse(result)


  def testInventoryAttrsParseWhenSkylabNotAliveWithUnknownAttrs(self):
    """Test inventory_attrs_parse when skylab not alive with unknown attrs."""
    ats._hostname_id_map = {'test_host1': 1, 'test_host2': 2}
    # Only HWID=test_hwid_1 is known to afe_host_attributes
    ats._hostattr_value_map = {(1, 'HWID'): 'test_hwid_1'}
    result = ats.inventory_attrs_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    expect_return = set([
        ats.AfeStaticHostAttr(host_id=1, attribute='HWID', value='test_hwid_1')
    ])
    self.assertEqual(result, expect_return)


  def testInventoryAttrsParseWhenSkylabAliveWithUnknownHost(self):
    """Test inventory_attrs_parse when skylab alive with unknown hosts."""
    # Host in inventory service does not exist in afe_hosts table.""
    ats._hostname_id_map = {}
    ats._hostattr_value_map = {}

    result = ats.inventory_attrs_parse(
        self.INVENTORY_DUT_INFOS, skylab_alive=False)
    self.assertFalse(result)


  def testInventoryAttrsParseWhenSkylabAliveWithUnknownAttrs(self):
    """Test inventory_attrs_parse when skylab alive with unknown attrs."""
    ats._hostname_id_map = {'test_host1': 1, 'test_host2': 2}

    # Only HWID=test_hwid_1 is known to afe_host_attributes,
    # serial_number=test_serial_num_1 is unknown. Unknown attribute will be
    # added to both afe_host_attributes and afe_static_host_attributes.
    ats._hostattr_value_map = {(1, 'HWID'): 'test_hwid_1'}
    result = ats.inventory_attrs_parse(
        [self.INVENTORY_DUT_INFOS[0]], skylab_alive=True)
    expect_return = set([
        ats.AfeStaticHostAttr(host_id=1, attribute='HWID', value='test_hwid_1'),
        ats.AfeStaticHostAttr(host_id=1,
                              attribute='serial_number',
                              value='test_serial_num_1')
    ])
    self.assertEqual(result, expect_return)

    # Only HWID=test_hwid_1 is known to afe_host_attributes,
    # serial_number=test_serial_num_1 has a different value in
    # afe_host_attributes. This attrbute will added to
    # afe_static_host_attributes and updated in afe_host_attributes.
    ats._hostattr_value_map = {(1, 'HWID'): 'test_hwid_1',
                               (1, 'serial_number'): 'test_serial_num_x'}
    result = ats.inventory_attrs_parse(
        [self.INVENTORY_DUT_INFOS[0]], skylab_alive=True)
    expect_return = set([
        ats.AfeStaticHostAttr(host_id=1, attribute='HWID', value='test_hwid_1'),
        ats.AfeStaticHostAttr(host_id=1,
                              attribute='serial_number',
                              value='test_serial_num_1')
    ])
    self.assertEqual(result, expect_return)


  def testInventoryAttrsParseWithEmptyValueAttr(self):
    """Test inventory_attrs_parse with empty value attribute."""
    ats._hostname_id_map = {'test_host1': 1, 'test_host2': 2}
    ats._hostattr_value_map = {(2, 'HWID'): 'test_hwid_2',
                               (2, 'serial_number'): 'test_serial_num_2'}
    # No matter whether skylab is alive or not, empty value will be skipped.
    expect_return = set([
        ats.AfeStaticHostAttr(host_id=2, attribute='HWID', value='test_hwid_2'),
        ats.AfeStaticHostAttr(host_id=2,
                              attribute='serial_number',
                              value='test_serial_num_2')
    ])

    result = ats.inventory_attrs_parse(
        [self.INVENTORY_DUT_INFOS[1]], skylab_alive=False)
    self.assertEqual(result, expect_return)

    result = ats.inventory_attrs_parse(
        [self.INVENTORY_DUT_INFOS[1]], skylab_alive=True)
    self.assertEqual(result, expect_return)


  def testUpdateAfeStaticHostAttributeWhenSkylabNotAliveWithDelete(self):
    """Test update_afe_static_host_attributes deletes when skylab not alive."""
    inventory_output = set()
    db_output = set([ats.AfeStaticHostAttr(
        host_id=1, attribute='test_attr', value='test_value')])
    ats._hostattr_value_map = {}
    result = ats.update_afe_static_host_attributes(
        inventory_output, db_output, skylab_alive=False)
    expect_return = [
        "DELETE FROM afe_static_host_attributes "
        "WHERE host_id=1 AND attribute='test_attr' AND value='test_value';"]
    self.assertEqual(result, expect_return)


  def testUpdateAfeStaticHostAttributeWhenSkylabNotAliveWithInsert(self):
    """Test update_afe_static_host_attributes inserts when skylab not alive."""
    inventory_output = set([ats.AfeStaticHostAttr(
        host_id=1, attribute='test_attr', value='test_value')])
    db_output = set()
    ats._hostattr_value_map = {}
    result = ats.update_afe_static_host_attributes(
        inventory_output, db_output, skylab_alive=False)
    expect_return = [
        "INSERT INTO afe_static_host_attributes "
        "(host_id, attribute, value) VALUES(1, 'test_attr', 'test_value');"]
    self.assertEqual(result, expect_return)


  def testUpdateAfeStaticHostAttributeWhenSkylabAliveWithDelete(self):
    """Test update_afe_static_host_attributes when skylab alive with deletes."""
    inventory_output = set()
    db_output = set([ats.AfeStaticHostAttr(
        host_id=1, attribute='test_attr', value='test_value')])
    ats._hostattr_value_map = {(1, 'test_attr'): 'test_value'}
    result = ats.update_afe_static_host_attributes(
        inventory_output, db_output, skylab_alive=True)
    expect_return = [
        "DELETE FROM afe_static_host_attributes "
        "WHERE host_id=1 AND attribute='test_attr' AND value='test_value';",
        "DELETE FROM afe_host_attributes "
        "WHERE host_id=1 AND attribute='test_attr' AND value='test_value';"
    ]
    self.assertEqual(result, expect_return)
    # Deleted entry will be removed from _hostattr_value_map
    self.assertEqual(ats._hostattr_value_map, {})


  def testUpdateAfeStaticHostAttributeWhenSkylabAliveWithInsert(self):
    """Test update_afe_static_host_attributes when skylab alive with inserts."""
    inventory_output = set([ats.AfeStaticHostAttr(
        host_id=1, attribute='test_attr', value='test_value')])
    db_output = set()

    # Attibute not exist in afe_host_attributes, insert it.
    ats._hostattr_value_map = {}
    result = ats.update_afe_static_host_attributes(
        inventory_output, db_output, skylab_alive=True)
    expect_return = [
        "INSERT INTO afe_static_host_attributes "
        "(host_id, attribute, value) VALUES(1, 'test_attr', 'test_value');",
        "INSERT INTO afe_host_attributes "
        "(host_id, attribute, value) VALUES(1, 'test_attr', 'test_value');"
    ]
    self.assertEqual(result, expect_return)

    # Attribute exists in afe_host_attributes but with different value.
    ats._hostattr_value_map = {(1, 'test_attr'): 'diff_value'}
    result = ats.update_afe_static_host_attributes(
        inventory_output, db_output, skylab_alive=True)
    expect_return = [
        "INSERT INTO afe_static_host_attributes "
        "(host_id, attribute, value) VALUES(1, 'test_attr', 'test_value');",
        "UPDATE afe_host_attributes SET value='test_value' "
        "WHERE host_id=1 AND attribute='test_attr';"
    ]
    self.assertEqual(result, expect_return)


if __name__ == '__main__':
  unittest.main()
