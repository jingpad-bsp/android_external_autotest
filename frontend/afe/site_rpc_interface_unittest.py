#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for frontend/afe/site_rpc_interface.py."""


import __builtin__
# The boto module is only available/used in Moblab for validation of cloud
# storage access. The module is not available in the test lab environment, 
# and the import error is handled.
try:
    import boto
except ImportError:
    boto = None
import ConfigParser
import datetime
import logging
import mox
import StringIO
import unittest

import common

from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models, model_logic, rpc_utils
from autotest_lib.client.common_lib import control_data, error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import lsbrelease_utils
from autotest_lib.client.common_lib import priorities
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe import rpc_interface, site_rpc_interface
from autotest_lib.server import utils
from autotest_lib.server.cros import provision
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.hosts import moblab_host


CLIENT = control_data.CONTROL_TYPE_NAMES.CLIENT
SERVER = control_data.CONTROL_TYPE_NAMES.SERVER


class SiteRpcInterfaceTest(mox.MoxTestBase,
                           frontend_test_utils.FrontendTestMixin):
    """Unit tests for functions in site_rpc_interface.py.

    @var _NAME: fake suite name.
    @var _BOARD: fake board to reimage.
    @var _BUILD: fake build with which to reimage.
    @var _PRIORITY: fake priority with which to reimage.
    """
    _NAME = 'name'
    _BOARD = 'link'
    _BUILD = 'link-release/R36-5812.0.0'
    _BUILDS = {provision.CROS_VERSION_PREFIX: _BUILD}
    _PRIORITY = priorities.Priority.DEFAULT
    _TIMEOUT = 24


    def setUp(self):
        super(SiteRpcInterfaceTest, self).setUp()
        self._SUITE_NAME = site_rpc_interface.canonicalize_suite_name(
            self._NAME)
        self.dev_server = self.mox.CreateMock(dev_server.ImageServer)
        self._frontend_common_setup(fill_data=False)


    def tearDown(self):
        self._frontend_common_teardown()


    def _setupDevserver(self):
        self.mox.StubOutClassWithMocks(dev_server, 'ImageServer')
        dev_server.resolve(self._BUILD).AndReturn(self.dev_server)


    def _mockDevServerGetter(self, get_control_file=True):
        self._setupDevserver()
        if get_control_file:
          self.getter = self.mox.CreateMock(
              control_file_getter.DevServerGetter)
          self.mox.StubOutWithMock(control_file_getter.DevServerGetter,
                                   'create')
          control_file_getter.DevServerGetter.create(
              mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(self.getter)


    def _mockRpcUtils(self, to_return, control_file_substring=''):
        """Fake out the autotest rpc_utils module with a mockable class.

        @param to_return: the value that rpc_utils.create_job_common() should
                          be mocked out to return.
        @param control_file_substring: A substring that is expected to appear
                                       in the control file output string that
                                       is passed to create_job_common.
                                       Default: ''
        """
        download_started_time = constants.DOWNLOAD_STARTED_TIME
        payload_finished_time = constants.PAYLOAD_FINISHED_TIME
        self.mox.StubOutWithMock(rpc_utils, 'create_job_common')
        rpc_utils.create_job_common(mox.And(mox.StrContains(self._NAME),
                                    mox.StrContains(self._BUILD)),
                            priority=self._PRIORITY,
                            timeout_mins=self._TIMEOUT*60,
                            max_runtime_mins=self._TIMEOUT*60,
                            control_type='Server',
                            control_file=mox.And(mox.StrContains(self._BOARD),
                                                 mox.StrContains(self._BUILD),
                                                 mox.StrContains(
                                                     control_file_substring)),
                            hostless=True,
                            keyvals=mox.And(mox.In(download_started_time),
                                            mox.In(payload_finished_time))
                            ).AndReturn(to_return)


    def testStageBuildFail(self):
        """Ensure that a failure to stage the desired build fails the RPC."""
        self._setupDevserver()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndRaise(
                dev_server.DevServerException())
        self.mox.ReplayAll()
        self.assertRaises(error.StageControlFileFailure,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None)


    def testGetControlFileFail(self):
        """Ensure that a failure to get needed control file fails the RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(error.ControlFileEmpty,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None)


    def testGetControlFileListFail(self):
        """Ensure that a failure to get needed control file fails the RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndRaise(error.NoControlFileList())
        self.mox.ReplayAll()
        self.assertRaises(error.NoControlFileList,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None)


    def testBadNumArgument(self):
        """Ensure we handle bad values for the |num| argument."""
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None,
                          num='goo')
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None,
                          num=[])
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          name=self._NAME,
                          board=self._BOARD,
                          builds=self._BUILDS,
                          pool=None,
                          num='5')



    def testCreateSuiteJobFail(self):
        """Ensure that failure to schedule the suite job fails the RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')

        self.dev_server.url().AndReturn('mox_url')
        self._mockRpcUtils(-1)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                builds=self._BUILDS, pool=None),
            -1)


    def testCreateSuiteJobSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')

        self.dev_server.url().AndReturn('mox_url')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                builds=self._BUILDS,
                                                pool=None),
            job_id)


    def testCreateSuiteJobNoHostCheckSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')

        self.dev_server.url().AndReturn('mox_url')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
          site_rpc_interface.create_suite_job(name=self._NAME,
                                              board=self._BOARD,
                                              builds=self._BUILDS,
                                              pool=None, check_hosts=False),
          job_id)

    def testCreateSuiteIntegerNum(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')

        self.dev_server.url().AndReturn('mox_url')
        job_id = 5
        self._mockRpcUtils(job_id, control_file_substring='num=17')
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                builds=self._BUILDS,
                                                pool=None,
                                                check_hosts=False,
                                                num=17),
            job_id)


    def testCreateSuiteJobControlFileSupplied(self):
        """Ensure we can supply the control file to create_suite_job."""
        self._mockDevServerGetter(get_control_file=False)

        self.dev_server.url().AndReturn('mox_url')
        self.dev_server.get_server_name(mox.IgnoreArg()).AndReturn('mox_url')
        self.dev_server.stage_artifacts(
                image=self._BUILD, artifacts=['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name='%s/%s' % (self._NAME,
                                                                self._BUILD),
                                                board=None,
                                                builds=self._BUILDS,
                                                pool=None,
                                                control_file='CONTROL FILE'),
            job_id)


    def setIsMoblab(self, is_moblab):
        """Set utils.is_moblab result.

        @param is_moblab: Value to have utils.is_moblab to return.
        """
        self.mox.StubOutWithMock(utils, 'is_moblab')
        utils.is_moblab().AndReturn(is_moblab)


    def testMoblabOnlyDecorator(self):
        """Ensure the moblab only decorator gates functions properly."""
        self.setIsMoblab(False)
        self.mox.ReplayAll()
        self.assertRaises(error.RPCException,
                          site_rpc_interface.get_config_values)


    def testGetConfigValues(self):
        """Ensure that the config object is properly converted to a dict."""
        self.setIsMoblab(True)
        config_mock = self.mox.CreateMockAnything()
        site_rpc_interface._CONFIG = config_mock
        config_mock.get_sections().AndReturn(['section1', 'section2'])
        config_mock.config = self.mox.CreateMockAnything()
        config_mock.config.items('section1').AndReturn([('item1', 'value1'),
                                                        ('item2', 'value2')])
        config_mock.config.items('section2').AndReturn([('item3', 'value3'),
                                                        ('item4', 'value4')])

        rpc_utils.prepare_for_serialization(
            {'section1' : [('item1', 'value1'),
                           ('item2', 'value2')],
             'section2' : [('item3', 'value3'),
                           ('item4', 'value4')]})
        self.mox.ReplayAll()
        site_rpc_interface.get_config_values()


    def testGetNetworkInfo(self):
        """Ensure the network info is properly converted to a dict."""
        self.setIsMoblab(True)

        self.mox.StubOutWithMock(site_rpc_interface, '_get_network_info')
        site_rpc_interface._get_network_info().AndReturn(('10.0.0.1', True))
        self.mox.StubOutWithMock(rpc_utils, 'prepare_for_serialization')

        rpc_utils.prepare_for_serialization(
               {'is_connected': True, 'server_ips': ['10.0.0.1']})
        self.mox.ReplayAll()
        site_rpc_interface.get_network_info()
        self.mox.VerifyAll()


    def testGetNetworkInfoWithNoIp(self):
        """Queries network info with no public IP address."""
        self.setIsMoblab(True)

        self.mox.StubOutWithMock(site_rpc_interface, '_get_network_info')
        site_rpc_interface._get_network_info().AndReturn((None, False))
        self.mox.StubOutWithMock(rpc_utils, 'prepare_for_serialization')

        rpc_utils.prepare_for_serialization(
               {'is_connected': False})
        self.mox.ReplayAll()
        site_rpc_interface.get_network_info()
        self.mox.VerifyAll()


    def testGetNetworkInfoWithNoConnectivity(self):
        """Queries network info with public IP address but no connectivity."""
        self.setIsMoblab(True)

        self.mox.StubOutWithMock(site_rpc_interface, '_get_network_info')
        site_rpc_interface._get_network_info().AndReturn(('10.0.0.1', False))
        self.mox.StubOutWithMock(rpc_utils, 'prepare_for_serialization')

        rpc_utils.prepare_for_serialization(
               {'is_connected': False, 'server_ips': ['10.0.0.1']})
        self.mox.ReplayAll()
        site_rpc_interface.get_network_info()
        self.mox.VerifyAll()


    def testGetCloudStorageInfo(self):
        """Ensure the cloud storage info is properly converted to a dict."""
        self.setIsMoblab(True)
        config_mock = self.mox.CreateMockAnything()
        site_rpc_interface._CONFIG = config_mock
        config_mock.get_config_value(
            'CROS', 'image_storage_server').AndReturn('gs://bucket1')
        config_mock.get_config_value(
            'CROS', 'results_storage_server', default=None).AndReturn(
                    'gs://bucket2')
        self.mox.StubOutWithMock(site_rpc_interface, '_get_boto_config')
        site_rpc_interface._get_boto_config().AndReturn(config_mock)
        config_mock.sections().AndReturn(['Credentials', 'b'])
        config_mock.options('Credentials').AndReturn(
            ['gs_access_key_id', 'gs_secret_access_key'])
        config_mock.get(
            'Credentials', 'gs_access_key_id').AndReturn('key')
        config_mock.get(
            'Credentials', 'gs_secret_access_key').AndReturn('secret')
        rpc_utils.prepare_for_serialization(
                {
                    'gs_access_key_id': 'key',
                    'gs_secret_access_key' : 'secret',
                    'use_existing_boto_file': True,
                    'image_storage_server' : 'gs://bucket1',
                    'results_storage_server' : 'gs://bucket2'
                })
        self.mox.ReplayAll()
        site_rpc_interface.get_cloud_storage_info()
        self.mox.VerifyAll()


    def testValidateCloudStorageInfo(self):
        """ Ensure the cloud storage info validation flow."""
        self.setIsMoblab(True)
        cloud_storage_info = {
            'use_existing_boto_file': False,
            'gs_access_key_id': 'key',
            'gs_secret_access_key': 'secret',
            'image_storage_server': 'gs://bucket1',
            'results_storage_server': 'gs://bucket2'}
        self.mox.StubOutWithMock(site_rpc_interface, '_is_valid_boto_key')
        self.mox.StubOutWithMock(site_rpc_interface, '_is_valid_bucket')
        site_rpc_interface._is_valid_boto_key(
                'key', 'secret').AndReturn((True, None))
        site_rpc_interface._is_valid_bucket(
                'key', 'secret', 'bucket1').AndReturn((True, None))
        site_rpc_interface._is_valid_bucket(
                'key', 'secret', 'bucket2').AndReturn((True, None))
        rpc_utils.prepare_for_serialization(
                {'status_ok': True })
        self.mox.ReplayAll()
        site_rpc_interface.validate_cloud_storage_info(cloud_storage_info)
        self.mox.VerifyAll()


    def testGetBucketNameFromUrl(self):
        """Gets bucket name from bucket URL."""
        self.assertEquals(
            'bucket_name-123',
            site_rpc_interface._get_bucket_name_from_url(
                    'gs://bucket_name-123'))
        self.assertEquals(
            'bucket_name-123',
            site_rpc_interface._get_bucket_name_from_url(
                    'gs://bucket_name-123/'))
        self.assertEquals(
            'bucket_name-123',
            site_rpc_interface._get_bucket_name_from_url(
                    'gs://bucket_name-123/a/b/c'))
        self.assertIsNone(site_rpc_interface._get_bucket_name_from_url(
            'bucket_name-123/a/b/c'))


    def testIsValidBotoKeyValid(self):
        """Tests the boto key validation flow."""
        if boto is None:
            logging.info('skip test since boto module not installed')
            return
        conn = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(boto, 'connect_gs')
        boto.connect_gs('key', 'secret').AndReturn(conn)
        conn.get_all_buckets().AndReturn(['a', 'b'])
        conn.close()
        self.mox.ReplayAll()
        valid, details = site_rpc_interface._is_valid_boto_key('key', 'secret')
        self.assertTrue(valid)
        self.mox.VerifyAll()


    def testIsValidBotoKeyInvalid(self):
        """Tests the boto key validation with invalid key."""
        if boto is None:
            logging.info('skip test since boto module not installed')
            return
        conn = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(boto, 'connect_gs')
        boto.connect_gs('key', 'secret').AndReturn(conn)
        conn.get_all_buckets().AndRaise(
                boto.exception.GSResponseError('bad', 'reason'))
        conn.close()
        self.mox.ReplayAll()
        valid, details = site_rpc_interface._is_valid_boto_key('key', 'secret')
        self.assertFalse(valid)
        self.assertEquals('The boto access key is not valid', details)
        self.mox.VerifyAll()


    def testIsValidBucketValid(self):
        """Tests the bucket vaildation flow."""
        if boto is None:
            logging.info('skip test since boto module not installed')
            return
        conn = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(boto, 'connect_gs')
        boto.connect_gs('key', 'secret').AndReturn(conn)
        conn.lookup('bucket').AndReturn('bucket')
        conn.close()
        self.mox.ReplayAll()
        valid, details = site_rpc_interface._is_valid_bucket(
                'key', 'secret', 'bucket')
        self.assertTrue(valid)
        self.mox.VerifyAll()


    def testIsValidBucketInvalid(self):
        """Tests the bucket validation flow with invalid key."""
        if boto is None:
            logging.info('skip test since boto module not installed')
            return
        conn = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(boto, 'connect_gs')
        boto.connect_gs('key', 'secret').AndReturn(conn)
        conn.lookup('bucket').AndReturn(None)
        conn.close()
        self.mox.ReplayAll()
        valid, details = site_rpc_interface._is_valid_bucket(
                'key', 'secret', 'bucket')
        self.assertFalse(valid)
        self.assertEquals("Bucket bucket does not exist.", details)
        self.mox.VerifyAll()


    def testGetShadowConfigFromPartialUpdate(self):
        """Tests getting shadow configuration based on partial upate."""
        partial_config = {
                'section1': [
                    ('opt1', 'value1'),
                    ('opt2', 'value2'),
                    ('opt3', 'value3'),
                    ('opt4', 'value4'),
                    ]
                }
        shadow_config_str = "[section1]\nopt2 = value2_1\nopt4 = value4_1"
        shadow_config = ConfigParser.ConfigParser()
        shadow_config.readfp(StringIO.StringIO(shadow_config_str))
        original_config = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(site_rpc_interface, '_read_original_config')
        self.mox.StubOutWithMock(site_rpc_interface, '_read_raw_config')
        site_rpc_interface._read_original_config().AndReturn(original_config)
        site_rpc_interface._read_raw_config(
                site_rpc_interface._CONFIG.shadow_file).AndReturn(shadow_config)
        original_config.get_config_value(
                'section1', 'opt1',
                allow_blank=True, default='').AndReturn('value1')
        original_config.get_config_value(
                'section1', 'opt2',
                allow_blank=True, default='').AndReturn('value2')
        original_config.get_config_value(
                'section1', 'opt3',
                allow_blank=True, default='').AndReturn('blah')
        original_config.get_config_value(
                'section1', 'opt4',
                allow_blank=True, default='').AndReturn('blah')
        self.mox.ReplayAll()
        shadow_config = site_rpc_interface._get_shadow_config_from_partial_update(
                partial_config)
        # opt1 same as the original.
        self.assertFalse(shadow_config.has_option('section1', 'opt1'))
        # opt2 reverts back to original
        self.assertFalse(shadow_config.has_option('section1', 'opt2'))
        # opt3 is updated from original.
        self.assertEquals('value3', shadow_config.get('section1', 'opt3'))
        # opt3 in shadow but updated again.
        self.assertEquals('value4', shadow_config.get('section1', 'opt4'))
        self.mox.VerifyAll()


    def testGetShadowConfigFromPartialUpdateWithNewSection(self):
        """
        Test getting shadown configuration based on partial update with new section.
        """
        partial_config = {
                'section2': [
                    ('opt5', 'value5'),
                    ('opt6', 'value6'),
                    ],
                }
        shadow_config_str = "[section1]\nopt2 = value2_1\n"
        shadow_config = ConfigParser.ConfigParser()
        shadow_config.readfp(StringIO.StringIO(shadow_config_str))
        original_config = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(site_rpc_interface, '_read_original_config')
        self.mox.StubOutWithMock(site_rpc_interface, '_read_raw_config')
        site_rpc_interface._read_original_config().AndReturn(original_config)
        site_rpc_interface._read_raw_config(
            site_rpc_interface._CONFIG.shadow_file).AndReturn(shadow_config)
        original_config.get_config_value(
                'section2', 'opt5',
                allow_blank=True, default='').AndReturn('value5')
        original_config.get_config_value(
                'section2', 'opt6',
                allow_blank=True, default='').AndReturn('blah')
        self.mox.ReplayAll()
        shadow_config = site_rpc_interface._get_shadow_config_from_partial_update(
                partial_config)
        # opt2 is still in shadow
        self.assertEquals('value2_1', shadow_config.get('section1', 'opt2'))
        # opt5 is not changed.
        self.assertFalse(shadow_config.has_option('section2', 'opt5'))
        # opt6 is updated.
        self.assertEquals('value6', shadow_config.get('section2', 'opt6'))
        self.mox.VerifyAll()


    def _mockReadFile(self, path, lines=[]):
        """Mock out reading a file line by line.

        @param path: Path of the file we are mock reading.
        @param lines: lines of the mock file that will be returned when
                      readLine() is called.
        """
        mockFile = self.mox.CreateMockAnything()
        for line in lines:
            mockFile.readline().AndReturn(line)
        mockFile.readline()
        mockFile.close()
        open(path).AndReturn(mockFile)


    def testUpdateConfig(self):
        """Ensure that updating the config works as expected."""
        self.setIsMoblab(True)
        site_rpc_interface.os = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(__builtin__, 'open')
        self._mockReadFile(global_config.DEFAULT_CONFIG_FILE)

        self.mox.StubOutWithMock(lsbrelease_utils, 'is_moblab')
        lsbrelease_utils.is_moblab().AndReturn(True)

        self._mockReadFile(global_config.DEFAULT_MOBLAB_FILE,
                           ['[section1]', 'item1: value1'])

        site_rpc_interface.os = self.mox.CreateMockAnything()
        site_rpc_interface.os.path = self.mox.CreateMockAnything()
        site_rpc_interface.os.path.exists(
                site_rpc_interface._CONFIG.shadow_file).AndReturn(
                True)
        mockShadowFile = self.mox.CreateMockAnything()
        mockShadowFileContents = StringIO.StringIO()
        mockShadowFile.__enter__().AndReturn(mockShadowFileContents)
        mockShadowFile.__exit__(mox.IgnoreArg(), mox.IgnoreArg(),
                                mox.IgnoreArg())
        open(site_rpc_interface._CONFIG.shadow_file,
             'w').AndReturn(mockShadowFile)
        site_rpc_interface.os.system('sudo reboot')

        self.mox.ReplayAll()
        site_rpc_interface.update_config_handler(
                {'section1' : [('item1', 'value1'),
                               ('item2', 'value2')],
                 'section2' : [('item3', 'value3'),
                               ('item4', 'value4')]})

        # item1 should not be in the new shadow config as its updated value
        # matches the original config's value.
        self.assertEquals(
                mockShadowFileContents.getvalue(),
                '[section2]\nitem3 = value3\nitem4 = value4\n\n'
                '[section1]\nitem2 = value2\n\n')


    def testResetConfig(self):
        """Ensure that reset opens the shadow_config file for writing."""
        self.setIsMoblab(True)
        config_mock = self.mox.CreateMockAnything()
        site_rpc_interface._CONFIG = config_mock
        config_mock.shadow_file = 'shadow_config.ini'
        self.mox.StubOutWithMock(__builtin__, 'open')
        mockFile = self.mox.CreateMockAnything()
        file_contents = self.mox.CreateMockAnything()
        mockFile.__enter__().AndReturn(file_contents)
        mockFile.__exit__(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg())
        open(config_mock.shadow_file, 'w').AndReturn(mockFile)
        site_rpc_interface.os = self.mox.CreateMockAnything()
        site_rpc_interface.os.system('sudo reboot')
        self.mox.ReplayAll()
        site_rpc_interface.reset_config_settings()


    def testSetBotoKey(self):
        """Ensure that the botokey path supplied is copied correctly."""
        self.setIsMoblab(True)
        boto_key = '/tmp/boto'
        site_rpc_interface.os.path = self.mox.CreateMockAnything()
        site_rpc_interface.os.path.exists(boto_key).AndReturn(
                True)
        site_rpc_interface.shutil = self.mox.CreateMockAnything()
        site_rpc_interface.shutil.copyfile(
                boto_key, site_rpc_interface.MOBLAB_BOTO_LOCATION)
        self.mox.ReplayAll()
        site_rpc_interface.set_boto_key(boto_key)


    def testSetLaunchControlKey(self):
        """Ensure that the Launch Control key path supplied is copied correctly.
        """
        self.setIsMoblab(True)
        launch_control_key = '/tmp/launch_control'
        site_rpc_interface.os = self.mox.CreateMockAnything()
        site_rpc_interface.os.path = self.mox.CreateMockAnything()
        site_rpc_interface.os.path.exists(launch_control_key).AndReturn(
                True)
        site_rpc_interface.shutil = self.mox.CreateMockAnything()
        site_rpc_interface.shutil.copyfile(
                launch_control_key,
                moblab_host.MOBLAB_LAUNCH_CONTROL_KEY_LOCATION)
        site_rpc_interface.os.system('sudo restart moblab-devserver-init')
        self.mox.ReplayAll()
        site_rpc_interface.set_launch_control_key(launch_control_key)


    def _get_records_for_sending_to_master(self):
        return [{'control_file': 'foo',
                 'control_type': 1,
                 'created_on': datetime.datetime(2014, 8, 21),
                 'drone_set': None,
                 'email_list': '',
                 'max_runtime_hrs': 72,
                 'max_runtime_mins': 1440,
                 'name': 'dummy',
                 'owner': 'autotest_system',
                 'parse_failed_repair': True,
                 'priority': 40,
                 'reboot_after': 0,
                 'reboot_before': 1,
                 'run_reset': True,
                 'run_verify': False,
                 'synch_count': 0,
                 'test_retry': 10,
                 'timeout': 24,
                 'timeout_mins': 1440,
                 'id': 1
                 }], [{
                    'aborted': False,
                    'active': False,
                    'complete': False,
                    'deleted': False,
                    'execution_subdir': '',
                    'finished_on': None,
                    'started_on': None,
                    'status': 'Queued',
                    'id': 1
                }]


    def _do_heartbeat_and_assert_response(self, shard_hostname='shard1',
                                          upload_jobs=(), upload_hqes=(),
                                          known_jobs=(), known_hosts=(),
                                          **kwargs):
        known_job_ids = [job.id for job in known_jobs]
        known_host_ids = [host.id for host in known_hosts]
        known_host_statuses = [host.status for host in known_hosts]

        retval = site_rpc_interface.shard_heartbeat(
            shard_hostname=shard_hostname,
            jobs=upload_jobs, hqes=upload_hqes,
            known_job_ids=known_job_ids, known_host_ids=known_host_ids,
            known_host_statuses=known_host_statuses)

        self._assert_shard_heartbeat_response(shard_hostname, retval,
                                              **kwargs)

        return shard_hostname


    def _assert_shard_heartbeat_response(self, shard_hostname, retval, jobs=[],
                                         hosts=[], hqes=[]):

        retval_hosts, retval_jobs = retval['hosts'], retval['jobs']

        expected_jobs = [
            (job.id, job.name, shard_hostname) for job in jobs]
        returned_jobs = [(job['id'], job['name'], job['shard']['hostname'])
                         for job in retval_jobs]
        self.assertEqual(returned_jobs, expected_jobs)

        expected_hosts = [(host.id, host.hostname) for host in hosts]
        returned_hosts = [(host['id'], host['hostname'])
                          for host in retval_hosts]
        self.assertEqual(returned_hosts, expected_hosts)

        retval_hqes = []
        for job in retval_jobs:
            retval_hqes += job['hostqueueentry_set']

        expected_hqes = [(hqe.id) for hqe in hqes]
        returned_hqes = [(hqe['id']) for hqe in retval_hqes]
        self.assertEqual(returned_hqes, expected_hqes)


    def _send_records_to_master_helper(
        self, jobs, hqes, shard_hostname='host1',
        exception_to_throw=error.UnallowedRecordsSentToMaster, aborted=False):
        job_id = rpc_interface.create_job(name='dummy', priority='Medium',
                                          control_file='foo',
                                          control_type=SERVER,
                                          test_retry=10, hostless=True)
        job = models.Job.objects.get(pk=job_id)
        shard = models.Shard.objects.create(hostname='host1')
        job.shard = shard
        job.save()

        if aborted:
            job.hostqueueentry_set.update(aborted=True)
            job.shard = None
            job.save()

        hqe = job.hostqueueentry_set.all()[0]
        if not exception_to_throw:
            self._do_heartbeat_and_assert_response(
                shard_hostname=shard_hostname,
                upload_jobs=jobs, upload_hqes=hqes)
        else:
            self.assertRaises(
                exception_to_throw,
                self._do_heartbeat_and_assert_response,
                shard_hostname=shard_hostname,
                upload_jobs=jobs, upload_hqes=hqes)


    def testSendingRecordsToMaster(self):
        """Send records to the master and ensure they are persisted."""
        jobs, hqes = self._get_records_for_sending_to_master()
        hqes[0]['status'] = 'Completed'
        self._send_records_to_master_helper(
            jobs=jobs, hqes=hqes, exception_to_throw=None)

        # Check the entry was actually written to db
        self.assertEqual(models.HostQueueEntry.objects.all()[0].status,
                         'Completed')


    def testSendingRecordsToMasterAbortedOnMaster(self):
        """Send records to the master and ensure they are persisted."""
        jobs, hqes = self._get_records_for_sending_to_master()
        hqes[0]['status'] = 'Completed'
        self._send_records_to_master_helper(
            jobs=jobs, hqes=hqes, exception_to_throw=None, aborted=True)

        # Check the entry was actually written to db
        self.assertEqual(models.HostQueueEntry.objects.all()[0].status,
                         'Completed')


    def testSendingRecordsToMasterJobAssignedToDifferentShard(self):
        """Ensure records that belong to a different shard are rejected."""
        jobs, hqes = self._get_records_for_sending_to_master()
        models.Shard.objects.create(hostname='other_shard')
        self._send_records_to_master_helper(
            jobs=jobs, hqes=hqes, shard_hostname='other_shard')


    def testSendingRecordsToMasterJobHqeWithoutJob(self):
        """Ensure update for hqe without update for it's job gets rejected."""
        _, hqes = self._get_records_for_sending_to_master()
        self._send_records_to_master_helper(
            jobs=[], hqes=hqes)


    def testSendingRecordsToMasterNotExistingJob(self):
        """Ensure update for non existing job gets rejected."""
        jobs, hqes = self._get_records_for_sending_to_master()
        jobs[0]['id'] = 3

        self._send_records_to_master_helper(
            jobs=jobs, hqes=hqes)


    def _createShardAndHostWithLabel(self, shard_hostname='shard1',
                                     host_hostname='host1',
                                     label_name='board:lumpy'):
        label = models.Label.objects.create(name=label_name)

        shard = models.Shard.objects.create(hostname=shard_hostname)
        shard.labels.add(label)

        host = models.Host.objects.create(hostname=host_hostname, leased=False)
        host.labels.add(label)

        return shard, host, label


    def _createJobForLabel(self, label):
        job_id = rpc_interface.create_job(name='dummy', priority='Medium',
                                          control_file='foo',
                                          control_type=CLIENT,
                                          meta_hosts=[label.name],
                                          dependencies=(label.name,))
        return models.Job.objects.get(id=job_id)


    def testShardHeartbeatFetchHostlessJob(self):
        """Create a hostless job and ensure it's not assigned to a shard."""
        shard1, host1, lumpy_label = self._createShardAndHostWithLabel(
            'shard1', 'host1', 'board:lumpy')

        label2 = models.Label.objects.create(name='bluetooth', platform=False)

        job1 = self._create_job(hostless=True)

        # Hostless jobs should be executed by the global scheduler.
        self._do_heartbeat_and_assert_response(hosts=[host1])


    def testShardRetrieveJobs(self):
        """Create jobs and retrieve them."""
        # should never be returned by heartbeat
        leased_host = models.Host.objects.create(hostname='leased_host',
                                                 leased=True)

        shard1, host1, lumpy_label = self._createShardAndHostWithLabel()
        shard2, host2, grumpy_label = self._createShardAndHostWithLabel(
            'shard2', 'host2', 'board:grumpy')

        leased_host.labels.add(lumpy_label)

        job1 = self._createJobForLabel(lumpy_label)

        job2 = self._createJobForLabel(grumpy_label)

        job_completed = self._createJobForLabel(lumpy_label)
        # Job is already being run, so don't sync it
        job_completed.hostqueueentry_set.update(complete=True)
        job_completed.hostqueueentry_set.create(complete=False)

        job_active = self._createJobForLabel(lumpy_label)
        # Job is already started, so don't sync it
        job_active.hostqueueentry_set.update(active=True)
        job_active.hostqueueentry_set.create(complete=False, active=False)

        self._do_heartbeat_and_assert_response(
            jobs=[job1], hosts=[host1], hqes=job1.hostqueueentry_set.all())

        self._do_heartbeat_and_assert_response(
            shard_hostname=shard2.hostname,
            jobs=[job2], hosts=[host2], hqes=job2.hostqueueentry_set.all())

        host3 = models.Host.objects.create(hostname='host3', leased=False)
        host3.labels.add(lumpy_label)

        self._do_heartbeat_and_assert_response(
            known_jobs=[job1], known_hosts=[host1], hosts=[host3])


    def testResendJobsAfterFailedHeartbeat(self):
        """Create jobs, retrieve them, fail on client, fetch them again."""
        shard1, host1, lumpy_label = self._createShardAndHostWithLabel()

        job1 = self._createJobForLabel(lumpy_label)

        self._do_heartbeat_and_assert_response(
            jobs=[job1],
            hqes=job1.hostqueueentry_set.all(), hosts=[host1])

        # Make sure it's resubmitted by sending last_job=None again
        self._do_heartbeat_and_assert_response(
            known_hosts=[host1],
            jobs=[job1], hqes=job1.hostqueueentry_set.all(), hosts=[])

        # Now it worked, make sure it's not sent again
        self._do_heartbeat_and_assert_response(
            known_jobs=[job1], known_hosts=[host1])

        job1 = models.Job.objects.get(pk=job1.id)
        job1.hostqueueentry_set.all().update(complete=True)

        # Job is completed, make sure it's not sent again
        self._do_heartbeat_and_assert_response(
            known_hosts=[host1])

        job2 = self._createJobForLabel(lumpy_label)

        # job2's creation was later, it should be returned now.
        self._do_heartbeat_and_assert_response(
            known_hosts=[host1],
            jobs=[job2], hqes=job2.hostqueueentry_set.all())

        self._do_heartbeat_and_assert_response(
            known_jobs=[job2], known_hosts=[host1])

        job2 = models.Job.objects.get(pk=job2.pk)
        job2.hostqueueentry_set.update(aborted=True)
        # Setting a job to a complete status will set the shard_id to None in
        # scheduler_models. We have to emulate that here, because we use Django
        # models in tests.
        job2.shard = None
        job2.save()

        self._do_heartbeat_and_assert_response(
            known_jobs=[job2], known_hosts=[host1],
            jobs=[job2],
            hqes=job2.hostqueueentry_set.all())

        models.Test.objects.create(name='platform_BootPerfServer:shard',
                                   test_type=1)
        self.mox.StubOutWithMock(utils, 'read_file')
        utils.read_file(mox.IgnoreArg()).AndReturn('')
        self.mox.ReplayAll()
        site_rpc_interface.delete_shard(hostname=shard1.hostname)

        self.assertRaises(
            models.Shard.DoesNotExist, models.Shard.objects.get, pk=shard1.id)

        job1 = models.Job.objects.get(pk=job1.id)
        lumpy_label = models.Label.objects.get(pk=lumpy_label.id)
        host1 = models.Host.objects.get(pk=host1.id)
        super_job = models.Job.objects.get(priority=priorities.Priority.SUPER)
        super_job_host = models.HostQueueEntry.objects.get(
                job_id=super_job.id)

        self.assertIsNone(job1.shard)
        self.assertEqual(len(lumpy_label.shard_set.all()), 0)
        self.assertIsNone(host1.shard)
        self.assertIsNotNone(super_job)
        self.assertEqual(super_job_host.host_id, host1.id)


    def testCreateListShard(self):
        """Retrieve a list of all shards."""
        lumpy_label = models.Label.objects.create(name='board:lumpy',
                                                  platform=True)
        stumpy_label = models.Label.objects.create(name='board:stumpy',
                                                  platform=True)

        shard_id = site_rpc_interface.add_shard(
            hostname='host1', labels='board:lumpy,board:stumpy')
        self.assertRaises(model_logic.ValidationError,
                          site_rpc_interface.add_shard,
                          hostname='host1', labels='board:lumpy,board:stumpy')
        shard = models.Shard.objects.get(pk=shard_id)
        self.assertEqual(shard.hostname, 'host1')
        self.assertEqual(shard.labels.values_list('pk')[0], (lumpy_label.id,))
        self.assertEqual(shard.labels.values_list('pk')[1], (stumpy_label.id,))

        self.assertEqual(site_rpc_interface.get_shards(),
                         [{'labels': ['board:lumpy','board:stumpy'],
                           'hostname': 'host1',
                           'id': 1}])


    def testResendHostsAfterFailedHeartbeat(self):
        """Check that master accepts resending updated records after failure."""
        shard1, host1, lumpy_label = self._createShardAndHostWithLabel()

        # Send the host
        self._do_heartbeat_and_assert_response(hosts=[host1])

        # Send it again because previous one didn't persist correctly
        self._do_heartbeat_and_assert_response(hosts=[host1])

        # Now it worked, make sure it isn't sent again
        self._do_heartbeat_and_assert_response(known_hosts=[host1])


if __name__ == '__main__':
  unittest.main()
