#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for host."""

# pylint: disable=missing-docstring

import sys
import unittest

import common
from autotest_lib.cli import cli_mock, host
from autotest_lib.client.common_lib import control_data
from autotest_lib.server import hosts
CLIENT = control_data.CONTROL_TYPE_NAMES.CLIENT
SERVER = control_data.CONTROL_TYPE_NAMES.SERVER

class host_ut(cli_mock.cli_unittest):
    def test_parse_lock_options_both_set(self):
        hh = host.host()
        class opt(object):
            lock = True
            unlock = True
        options = opt()
        self.usage = "unused"
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.god.mock_io()
        self.assertRaises(cli_mock.ExitException,
                          hh._parse_lock_options, options)
        self.god.unmock_io()


    def test_cleanup_labels_with_platform(self):
        labels = ['l0', 'l1', 'l2', 'p0', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels, 'p0'))


    def test_cleanup_labels_no_platform(self):
        labels = ['l0', 'l1', 'l2', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels))


    def test_cleanup_labels_with_non_avail_platform(self):
        labels = ['l0', 'l1', 'l2', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels, 'p0'))


class host_list_unittest(cli_mock.cli_unittest):
    def test_parse_host_not_required(self):
        hl = host.host_list()
        sys.argv = ['atest']
        (options, leftover) = hl.parse()
        self.assertEqual([], hl.hosts)
        self.assertEqual([], leftover)


    def test_parse_with_hosts(self):
        hl = host.host_list()
        mfile = cli_mock.create_file('host0\nhost3\nhost4\n')
        sys.argv = ['atest', 'host1', '--mlist', mfile.name, 'host3']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['host0', 'host1','host3', 'host4'],
                                hl.hosts)
        self.assertEqual(leftover, [])
        mfile.clean()


    def test_parse_with_labels(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label0']
        (options, leftover) = hl.parse()
        self.assertEqual(['label0'], hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_multi_labels(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label0,label2']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['label0', 'label2'], hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_escaped_commas_label(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label\\,0']
        (options, leftover) = hl.parse()
        self.assertEqual(['label,0'], hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_escaped_commas_multi_labels(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label\\,0,label\\,2']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['label,0', 'label,2'], hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_both(self):
        hl = host.host_list()
        mfile = cli_mock.create_file('host0\nhost3\nhost4\n')
        sys.argv = ['atest', 'host1', '--mlist', mfile.name, 'host3',
                    '--label', 'label0']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['host0', 'host1','host3', 'host4'],
                                hl.hosts)
        self.assertEqual(['label0'], hl.labels)
        self.assertEqual(leftover, [])
        mfile.clean()


    def test_execute_list_all_no_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list', '--ignore_site_file'],
                     rpcs=[('get_hosts', {},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': None,
                              u'shard': None,
                              u'id': 1},
                             {u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2}])],
                     out_words_ok=['host0', 'host1', 'Ready',
                                   'plat1', 'False', 'True', 'None'])


    def test_execute_list_all_with_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list', '--ignore_site_file'],
                     rpcs=[('get_hosts', {},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label0', u'label1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': None,
                              u'shard': None,
                              u'id': 1},
                             {u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 2}])],
                     out_words_ok=['host0', 'host1', 'Ready', 'plat1',
                                   'label0', 'label1', 'label2', 'label3',
                                   'False', 'True', 'None'])


    def test_execute_list_filter_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__in': ['host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True', 'None'],
                     out_words_no=['host0', 'host2',
                                   'label1', 'label4', 'False'])


    def test_execute_list_filter_two_hosts(self):
        mfile = cli_mock.create_file('host2')
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--mlist', mfile.name, '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])
        mfile.clean()


    def test_execute_list_filter_two_hosts_one_not_found(self):
        mfile = cli_mock.create_file('host2')
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--mlist', mfile.name, '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['Ready', 'plat1',
                                   'label3', 'label4', 'True', 'None'],
                     out_words_no=['host1', 'False'],
                     err_words_ok=['host1'])
        mfile.clean()


    def test_execute_list_filter_two_hosts_none_found(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           'host1', 'host2', '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host1', 'host2'])


    def test_execute_list_filter_label(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'shard': None,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_multi_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label2',
                                                              'label3']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat0',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host3',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label2', u'plat2'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat2',
                              u'id': 4}])],
                     out_words_ok=['host1', 'host3', 'Ready', 'plat0',
                                   'label2', 'label3', 'plat2', 'None'],
                     out_words_no=['host2', 'label4', 'False', 'plat1'])


    def test_execute_list_filter_three_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2, label4',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label2',
                                                              'label3',
                                                              'label4']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label2', u'label4',
                                          u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 3}])],
                     out_words_ok=['host2', 'plat1',
                                   'label2', 'label3', 'label4', 'None'],
                     out_words_no=['host1', 'host3'])


    def test_execute_list_filter_wild_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts',
                            {'labels__name__startswith': 'label'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': 1,
                              u'shard': None,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label2', u'label4',
                                          u'plat1'],
                              u'invalid': 0,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host2', 'plat1',
                                   'label2', 'label3', 'label4', 'None'],
                     out_words_no=['host1', 'host3'])


    def test_execute_list_filter_multi_labels_no_results(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2, ', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label2',
                                                              'label3']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['host1', 'host2', 'host3',
                                   'label2', 'label3', 'label4'])


    def test_execute_list_filter_label_and_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-b', 'label3', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'lock_reason': u'',
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_label_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-b', 'label3', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host1', 'host2'])


    def test_execute_list_filter_status(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-s', 'Ready', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Ready']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])



    def test_execute_list_filter_status_and_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-s', 'Ready', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Ready'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_status_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--status', 'Repair',
                           'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Repair'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host2'])


    def test_execute_list_filter_statuses_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--status', 'Repair',
                           'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Repair'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host2'])


    def test_execute_list_filter_locked(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--locked', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'locked': True,
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'shard': None,
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_unlocked(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '--unlocked', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'locked': False},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'shard': None,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'False',
                                   'host2', 'label4', 'None'],
                     out_words_no=['host0', 'label1', 'True'])


class host_stat_unittest(cli_mock.cli_unittest):
    def test_execute_stat_two_hosts(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'shard': None,
                              u'platform': u'plat1',
                              u'id': 3,
                              u'attributes': {}}]),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'shard': None,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2,
                              u'attributes': {}}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'plat0', 'plat1',
                                   'Everyone', 'acl0', 'label0'])


    def test_execute_stat_one_bad_host_verbose(self):
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0',
                           'host1', '-v', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            []),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2,
                              u'attributes': {}}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'plat0',
                                   'Everyone', 'acl0', 'label0'],
                     out_words_no=['host1'],
                     err_words_ok=['host1', 'Unknown host'],
                     err_words_no=['host0'])


    def test_execute_stat_one_bad_host(self):
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            []),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2,
                              u'attributes': {}}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'plat0',
                                   'Everyone', 'acl0', 'label0'],
                     out_words_no=['host1'],
                     err_words_ok=['host1', 'Unknown host'],
                     err_words_no=['host0'])


    def test_execute_stat_wildcard(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'ho*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3,
                              u'attributes': {}},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2,
                              u'attributes': {}}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'plat0', 'plat1',
                                   'Everyone', 'acl0', 'label0'])


    def test_execute_stat_wildcard_and_host(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'ho*', 'newhost0',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'newhost0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'newhost0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'lock_reason': u'',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 5,
                              u'attributes': {}}]),
                           ('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3,
                              u'attributes': {}},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_reason': u'',
                              u'protection': 'No protection',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2,
                              u'attributes': {}}]),
                           ('get_acl_groups', {'hosts__hostname': 'newhost0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'newhost0', 'host1'],
                              u'id': 42,
                              u'name': u'my_acl',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'my favorite acl',
                              u'hosts': [u'newhost0'],
                              u'id': 2,
                              u'name': u'acl10',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'newhost0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'newhost0',
                                   'plat0', 'plat1',
                                   'Everyone', 'acl10', 'label0'])


class host_jobs_unittest(cli_mock.cli_unittest):
    def test_execute_jobs_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'host0',
                           '--ignore_site_file'],
                     rpcs=[('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': CLIENT,
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': CLIENT,
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


    def test_execute_jobs_wildcard(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'ho*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_host_queue_entries',
                            {'host__hostname': 'host1', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host1',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': CLIENT,
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host1',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': CLIENT,
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}]),
                           ('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': CLIENT,
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': CLIENT,
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


    def test_execute_jobs_one_host_limit(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'host0',
                           '--ignore_site_file', '-q', '10'],
                     rpcs=[('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 10,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': CLIENT,
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': CLIENT,
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


class host_mod_unittest(cli_mock.cli_unittest):
    def test_execute_lock_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'mod', '--lock', 'host0'],
                     rpcs=[('modify_host', {'id': 'host0', 'locked': True},
                            True, None)],
                     out_words_ok=['Locked', 'host0'])


    def test_execute_unlock_two_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'mod', '-u', 'host0,host1'],
                     rpcs=[('modify_host', {'id': 'host1', 'locked': False,
                                            'lock_reason': ''},
                            True, None),
                           ('modify_host', {'id': 'host0', 'locked': False,
                                            'lock_reason': ''},
                            True, None)],
                     out_words_ok=['Unlocked', 'host0', 'host1'])


    def test_execute_force_lock_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'mod', '--lock',
                           '--force_modify_locking', 'host0'],
                     rpcs=[('modify_host',
                            {'id': 'host0', 'locked': True,
                             'force_modify_locking': True},
                            True, None)],
                     out_words_ok=['Locked', 'host0'])


    def test_execute_force_unlock_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'mod', '--unlock',
                           '--force_modify_locking', 'host0'],
                     rpcs=[('modify_host',
                            {'id': 'host0', 'locked': False,
                             'force_modify_locking': True,
                             'lock_reason': ''},
                            True, None)],
                     out_words_ok=['Unlocked', 'host0'])


    def test_execute_lock_unknown_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'mod', '-l', 'host0,host1',
                           'host2'],
                     rpcs=[('modify_host', {'id': 'host2', 'locked': True},
                            True, None),
                           ('modify_host', {'id': 'host1', 'locked': True},
                            False, 'DoesNotExist: Host matching '
                            'query does not exist.'),
                           ('modify_host', {'id': 'host0', 'locked': True},
                            True, None)],
                     out_words_ok=['Locked', 'host0', 'host2'],
                     err_words_ok=['Host', 'matching', 'query', 'host1'])


    def test_execute_protection_hosts(self):
        mfile = cli_mock.create_file('host0\nhost1,host2\nhost3 host4')
        try:
            self.run_cmd(argv=['atest', 'host', 'mod', '--protection',
                               'Do not repair', 'host5' ,'--mlist', mfile.name,
                               'host1', 'host6'],
                         rpcs=[('modify_host', {'id': 'host6',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host5',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host4',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host3',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host2',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host1',
                                                'protection': 'Do not repair'},
                                True, None),
                               ('modify_host', {'id': 'host0',
                                                'protection': 'Do not repair'},
                                True, None)],
                         out_words_ok=['Do not repair', 'host0', 'host1',
                                       'host2', 'host3', 'host4', 'host5',
                                       'host6'])
        finally:
            mfile.clean()

    def test_execute_attribute_host(self):
        self.run_cmd(argv=['atest', 'host', 'mod', 'host0', '--attribute',
                           'foo=bar'],
                     rpcs=[('modify_host', {'id': 'host0'}, True, None),
                           ('set_host_attribute', {'hostname': 'host0',
                                                   'attribute': 'foo',
                                                   'value': 'bar'},
                            True, None)],
                     out_words_ok=[])


class host_create_unittest(cli_mock.cli_unittest):
    _out = ['Added', 'host', 'localhost']
    _command = ['atest', 'host', 'create', 'localhost']

    def _mock_host(self, platform=None, labels=[]):
        mock_host = self.god.create_mock_class(hosts.Host, 'Host')
        hosts.create_host = self.god.create_mock_function('create_host')
        hosts.create_host.expect_any_call().and_return(mock_host)
        mock_host.get_platform.expect_call().and_return(platform)
        mock_host.get_labels.expect_call().and_return(labels)
        return mock_host


    def _mock_testbed(self, platform=None, labels=[]):
        mock_tb = self.god.create_mock_class(hosts.TestBed, 'TestBed')
        hosts.create_testbed = self.god.create_mock_function('create_testbed')
        hosts.create_testbed.expect_any_call().and_return(mock_tb)
        mock_tb.get_platform.expect_call().and_return(platform)
        mock_tb.get_labels.expect_call().and_return(labels)
        return mock_tb


    def _gen_rpcs_for_label(self, label, platform=False):
        rpcs = [
            ('get_labels', {'name': label}, True, []),
            ('add_label', {'name': label, 'platform': platform}, True, None)
        ]
        return rpcs


    def _gen_expected_rpcs(self, hosts=None, locked=False,
                           lock_reason=None, platform=None, labels=None,
                           acls=None, protection=None, serials=None):
        """Build a list of expected RPC calls based on values to host command.

        @param hosts: list of hostname being created (default ['localhost'])
        @param locked: end state of host (bool)
        @param lock_reason: reason for host to be locked
        @param platform: platform label
        @param labels: list of host labels (excluding platform)
        @param acls: list of host acls
        @param protection: host protection level

        @return: list of expect rpc calls (each call is (op, args, success,
            result))
        """
        rpcs = []
        hosts = hosts[:] if hosts else ['localhost']
        hosts.reverse() # No idea why
        lock_reason = lock_reason or 'Forced lock on device creation'
        acls = acls or []
        labels = labels or []

        if platform:
            rpcs += self._gen_rpcs_for_label(platform, platform=True)
        for label in labels:
            rpcs += self._gen_rpcs_for_label(label) * len(hosts)

        for acl in acls:
            rpcs.append(('get_acl_groups', {'name': acl}, True, []))
            rpcs.append(('add_acl_group', {'name': acl}, True, None))

        for host in hosts:
            add_args = {
                'hostname': host,
                'status': 'Ready',
                'locked': True,
                'lock_reason': lock_reason,
            }
            if protection:
                add_args['protection'] = protection
            rpcs.append(('add_host', add_args, True, None))

            if labels or platform:
                rpcs.append((
                    'host_add_labels',
                    {
                        'id': host,
                        'labels': labels + [platform] if platform else labels,
                    },
                    True,
                    None
                ))

        if serials:
            for host in hosts:
                rpcs.append((
                    'set_host_attribute',
                    {
                        'hostname': host,
                        'attribute': 'serials',
                        'value': ','.join(serials),
                    },
                    True,
                    None
                ))

        for acl in acls:
            for host in hosts:
                rpcs.append((
                    'acl_group_add_hosts',
                    {
                        'hosts': [host],
                        'id': acl,
                    },
                    True,
                    None,
                ))

        if not locked:
            for host in hosts:
                rpcs.append((
                    'modify_host',
                    {
                        'id': host,
                        'locked': False,
                        'lock_reason': '',
                    },
                    True,
                    None,
                ))
        return rpcs


    def test_create_simple(self):
        self._mock_host()
        rpcs = self._gen_expected_rpcs()
        self.run_cmd(argv=self._command, rpcs=rpcs, out_words_ok=self._out)


    def test_create_locked(self):
        self._mock_host()
        lock_reason = 'Because I said so.'
        rpcs = self._gen_expected_rpcs(locked=True,
                                                   lock_reason=lock_reason)
        self.run_cmd(argv=self._command + ['-l', '-r', lock_reason],
                     rpcs=rpcs, out_words_ok=self._out)


    def test_create_discovered_platform(self):
        self._mock_host(platform='some_platform')
        rpcs = self._gen_expected_rpcs(platform='some_platform')
        self.run_cmd(argv=self._command, rpcs=rpcs, out_words_ok=self._out)


    def test_create_specified_platform(self):
        self._mock_host()
        rpcs = self._gen_expected_rpcs(platform='some_platform')
        self.run_cmd(argv=self._command + ['-t', 'some_platform'], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_specified_platform_overrides_discovered_platform(self):
        self._mock_host(platform='wrong_platform')
        rpcs = self._gen_expected_rpcs(platform='some_platform')
        self.run_cmd(argv=self._command + ['-t', 'some_platform'], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_discovered_labels(self):
        labels = ['label0', 'label1']
        self._mock_host(labels=labels)
        rpcs = self._gen_expected_rpcs(labels=labels)
        self.run_cmd(argv=self._command, rpcs=rpcs, out_words_ok=self._out)


    def test_create_specified_labels(self):
        labels = ['label0', 'label1']
        self._mock_host()
        rpcs = self._gen_expected_rpcs(labels=labels)
        self.run_cmd(argv=self._command + ['-b', ','.join(labels)], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_specified_labels_from_file(self):
        labels = ['label0', 'label1']
        self._mock_host()
        rpcs = self._gen_expected_rpcs(labels=labels)
        labelsf = cli_mock.create_file(','.join(labels))
        try:
            self.run_cmd(argv=self._command + ['-B', labelsf.name], rpcs=rpcs,
                         out_words_ok=self._out)
        finally:
            labelsf.clean()

    def test_create_specified_discovered_labels_combine(self):
        labels = ['label0', 'label1']
        self._mock_host(labels=labels[0:1])
        rpcs = self._gen_expected_rpcs(labels=labels)
        self.run_cmd(argv=self._command + ['-b', labels[1]], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_acls(self):
        acls = ['acl0', 'acl1']
        self._mock_host()
        rpcs = self._gen_expected_rpcs(acls=acls)
        self.run_cmd(argv=self._command + ['-a', ','.join(acls)], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_acls_from_file(self):
        acls = ['acl0', 'acl1']
        self._mock_host()
        rpcs = self._gen_expected_rpcs(acls=acls)
        aclsf = cli_mock.create_file(','.join(acls))
        try:
            self.run_cmd(argv=self._command + ['-A', aclsf.name], rpcs=rpcs,
                         out_words_ok=self._out)
        finally:
            aclsf.clean()


    def test_create_protection(self):
        protection = 'Do not repair'
        self._mock_host()
        rpcs = self._gen_expected_rpcs(protection=protection)
        self.run_cmd(argv=self._command + ['-p', protection], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_protection_invalid(self):
        protection = 'Invalid protection'
        rpcs = self._gen_expected_rpcs()
        self.run_cmd(argv=self._command + ['-p', protection], exit_code=2,
                     err_words_ok=['invalid', 'choice'] + protection.split())


    def test_create_one_serial(self):
        serial = 'device0'
        self._mock_host()
        rpcs = self._gen_expected_rpcs(serials=[serial])
        self.run_cmd(argv=self._command + ['-s', serial], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_multiple_serials(self):
        serials = ['device0', 'device1']
        self._mock_testbed()
        rpcs = self._gen_expected_rpcs(serials=serials)
        self.run_cmd(argv=self._command + ['-s', ','.join(serials)], rpcs=rpcs,
                     out_words_ok=self._out)


    def test_create_multiple_simple_hosts(self):
        mock_host = self._mock_host()
        hosts.create_host.expect_any_call().and_return(mock_host)
        mock_host.get_platform.expect_call()
        mock_host.get_labels.expect_call().and_return([])

        hostnames = ['localhost', '127.0.0.1']
        rpcs = self._gen_expected_rpcs(hosts=hostnames)

        self.run_cmd(argv=['atest', 'host', 'create'] + hostnames,
                     rpcs=rpcs[0:4],
                     out_words_ok=['Added', 'hosts'] + hostnames)


    def test_create_complex(self):
        lock_reason = 'Because I said so.'
        platform = 'some_platform'
        labels = ['label0', 'label1', 'label2']
        acls = ['acl0', 'acl1']
        protection = 'Do not verify'
        labelsf = cli_mock.create_file(labels[2])
        aclsf = cli_mock.create_file(acls[1])
        cmd_args = ['-l', '-r', lock_reason, '-t', platform, '-b', labels[1],
                    '-B', labelsf.name, '-a', acls[0], '-A', aclsf.name, '-p',
                    protection]
        self._mock_host(labels=labels[0:1])
        rpcs = self._gen_expected_rpcs(locked=True, lock_reason=lock_reason,
                                       acls=acls, labels=labels,
                                       platform=platform, protection=protection)

        try:
            self.run_cmd(argv=self._command + cmd_args, rpcs=rpcs,
                         out_words_ok=self._out)
        finally:
            labelsf.clean()
            aclsf.clean()


if __name__ == '__main__':
    unittest.main()
