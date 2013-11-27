# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import json
import mox
import time
import unittest
import urllib2

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import site_utils


_OPEN_STATUS_VALUES = [
    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up (cross your fingers)",
      "can_commit_freely": true,
      "general_state": "open"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is on fire",
      "can_commit_freely": true,
      "general_state": "throttled"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up despite deadboard",
      "can_commit_freely": true,
      "general_state": "open"
    }
    ''',
]

_CLOSED_STATUS_VALUES = [
    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is down for spite",
      "can_commit_freely": false,
      "general_state": "closed"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is down even for [deadboard]",
      "can_commit_freely": false,
      "general_state": "closed"
    }
    ''',
]

_DEADBOARD_STATUS_VALUES = [
    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up except for [deadboard]",
      "can_commit_freely": false,
      "general_state": "open"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "liveboard is good, but [deadboard] is bad",
      "can_commit_freely": false,
      "general_state": "open"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up [deadboard otherboard]",
      "can_commit_freely": false,
      "general_state": "open"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up [otherboard deadboard]",
      "can_commit_freely": false,
      "general_state": "open"
    }
    ''',

    '''
    {
      "username": "fizzbin@google.com",
      "date": "2013-11-16 00:25:23.511208",
      "message": "Lab is up [first deadboard last]",
      "can_commit_freely": false,
      "general_state": "open"
    }
    ''',
]


_FAKE_URL = 'ignore://not.a.url'


class _FakeURLResponse(object):

    """Everything needed to pretend to be a response from urlopen().

    Creates a StringIO instance to handle the File operations.

    N.B.  StringIO is lame:  we can't inherit from it (super won't
    work), and it doesn't implement __getattr__(), either.  So, we
    have to manually forward calls to the StringIO object.  This
    forwards only what empirical testing says is required; YMMV.

    """

    def __init__(self, code, buffer):
        self._stringio = StringIO.StringIO(buffer)
        self._code = code


    def read(self, size=-1):
        """Standard file-like read operation.

        @param size size for read operation.
        """
        return self._stringio.read(size)


    def getcode(self):
        """Get URL HTTP response code."""
        return self._code


class GetStatusTest(mox.MoxTestBase):

    """Test case for _get_lab_status().

    We mock out dependencies on urllib2 and time.sleep(), and
    confirm that the function returns the proper JSON representation
    for a pre-defined response.

    """

    def setUp(self):
        super(GetStatusTest, self).setUp()
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        self.mox.StubOutWithMock(time, 'sleep')


    def test_success(self):
        """Test that successful calls to urlopen() succeed."""
        json_string = _OPEN_STATUS_VALUES[0]
        json_value = json.loads(json_string)
        urllib2.urlopen(mox.IgnoreArg()).AndReturn(
                _FakeURLResponse(200, json_string))
        self.mox.ReplayAll()
        result = site_utils._get_lab_status(_FAKE_URL)
        self.mox.VerifyAll()
        self.assertEqual(json_value, result)


    def test_retry_ioerror(self):
        """Test that an IOError retries at least once."""
        json_string = _OPEN_STATUS_VALUES[0]
        json_value = json.loads(json_string)
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(
                IOError('Fake I/O error for a fake URL'))
        time.sleep(mox.IgnoreArg()).AndReturn(None)
        urllib2.urlopen(mox.IgnoreArg()).AndReturn(
                _FakeURLResponse(200, json_string))
        self.mox.ReplayAll()
        result = site_utils._get_lab_status(_FAKE_URL)
        self.mox.VerifyAll()
        self.assertEqual(json_value, result)


    def test_retry_http_internal_error(self):
        """Test that an HTTP error retries at least once."""
        json_string = _OPEN_STATUS_VALUES[0]
        json_value = json.loads(json_string)
        urllib2.urlopen(mox.IgnoreArg()).AndReturn(
                _FakeURLResponse(500, ''))
        time.sleep(mox.IgnoreArg()).AndReturn(None)
        urllib2.urlopen(mox.IgnoreArg()).AndReturn(
                _FakeURLResponse(200, json_string))
        self.mox.ReplayAll()
        result = site_utils._get_lab_status(_FAKE_URL)
        self.mox.VerifyAll()
        self.assertEqual(json_value, result)


    def test_failure_ioerror(self):
        """Test that there's a failure if urlopen() never succeeds."""
        json_string = _OPEN_STATUS_VALUES[0]
        json_value = json.loads(json_string)
        for _ in range(site_utils._MAX_LAB_STATUS_ATTEMPTS):
            urllib2.urlopen(mox.IgnoreArg()).AndRaise(
                    IOError('Fake I/O error for a fake URL'))
            time.sleep(mox.IgnoreArg()).AndReturn(None)
        self.mox.ReplayAll()
        result = site_utils._get_lab_status(_FAKE_URL)
        self.mox.VerifyAll()
        self.assertEqual(None, result)


    def test_failure_http_internal_error(self):
        """Test that there's a failure for a permanent HTTP error."""
        json_string = _OPEN_STATUS_VALUES[0]
        json_value = json.loads(json_string)
        for _ in range(site_utils._MAX_LAB_STATUS_ATTEMPTS):
            urllib2.urlopen(mox.IgnoreArg()).AndReturn(
                    _FakeURLResponse(404, 'Not here, never gonna be'))
            time.sleep(mox.IgnoreArg()).InAnyOrder().AndReturn(None)
        self.mox.ReplayAll()
        result = site_utils._get_lab_status(_FAKE_URL)
        self.mox.VerifyAll()
        self.assertEqual(None, result)


class DecodeStatusTest(unittest.TestCase):

    """Test case for _decode_lab_status().

    Testing covers three distinct possible states:
     1. Lab is up.  All calls to _decode_lab_status() will
        succeed without raising an exception.
     2. Lab is down.  All calls to _decode_lab_status() will
        fail with LabIsDownException.
     3. Board disabled.  Calls to _decode_lab_status() will
        succeed, except that board 'deadboard' will raise
        BoardIsDisabledException.

    """

    def _assert_lab_open(self, lab_status):
        """Test that open status values are handled properly.

        Test that _decode_lab_status() succeeds when the lab status
        is up.

        @param lab_status JSON value describing lab status.

        """
        site_utils._decode_lab_status(lab_status, None)
        site_utils._decode_lab_status(lab_status, 'liveboard')
        site_utils._decode_lab_status(lab_status, 'deadboard')


    def _assert_lab_closed(self, lab_status):
        """Test that closed status values are handled properly.

        Test that _decode_lab_status() raises LabIsDownException
        when the lab status is down.

        @param lab_status JSON value describing lab status.

        """
        with self.assertRaises(site_utils.LabIsDownException):
            site_utils._decode_lab_status(lab_status, None)
        with self.assertRaises(site_utils.LabIsDownException):
            site_utils._decode_lab_status(lab_status, 'liveboard')
        with self.assertRaises(site_utils.LabIsDownException):
            site_utils._decode_lab_status(lab_status, 'deadboard')


    def _assert_lab_deadboard(self, lab_status):
        """Test that disabled boards are handled properly.

        Test that _decode_lab_status() raises
        BoardIsDisabledException for board 'deadboard' and
        succeeds otherwise.

        @param lab_status JSON value describing lab status.

        """
        site_utils._decode_lab_status(lab_status, None)
        site_utils._decode_lab_status(lab_status, 'liveboard')
        with self.assertRaises(site_utils.BoardIsDisabledException):
            site_utils._decode_lab_status(lab_status, 'deadboard')


    def _assert_lab_status(self, test_values, checker):
        """General purpose test for _decode_lab_status().

        Decode each JSON string in `test_values`, and call the
        `checker` function to test the corresponding status is
        correctly handled.

        @param test_values Array of JSON encoded strings representing
                           lab status.
        @param checker Function to be called against each of the lab
                       status values in the `test_values` array.

        """
        for s in test_values:
            lab_status = json.loads(s)
            checker(lab_status)


    def test_open_lab(self):
        """Test that open lab status values are handled correctly."""
        self._assert_lab_status(_OPEN_STATUS_VALUES,
                                self._assert_lab_open)


    def test_closed_lab(self):
        """Test that closed lab status values are handled correctly."""
        self._assert_lab_status(_CLOSED_STATUS_VALUES,
                                self._assert_lab_closed)


    def test_dead_board(self):
        """Test that disabled boards are handled correctly."""
        self._assert_lab_status(_DEADBOARD_STATUS_VALUES,
                                self._assert_lab_deadboard)


class CheckStatusTest(mox.MoxTestBase):

    """Test case for `check_lab_status()`.

    We mock out dependencies on `global_config.global_config()`,
    `_get_lab_status()` and confirm that the function succeeds or
    fails as expected.

    N.B.  We don't mock `_decode_lab_status()`; if DecodeStatusTest
    is failing, this test may fail, too.

    """

    def setUp(self):
        super(CheckStatusTest, self).setUp()
        self.mox.StubOutWithMock(global_config.global_config,
                                 'get_config_value')
        self.mox.StubOutWithMock(site_utils, '_get_lab_status')


    def _setup_not_cautotest(self):
        """Set up to mock the "we're not on cautotest" case."""
        global_config.global_config.get_config_value(
                'SERVER', 'hostname').AndReturn('not-cautotest')


    def _setup_no_status(self):
        """Set up to mock lab status as unavailable."""
        global_config.global_config.get_config_value(
                'SERVER', 'hostname').AndReturn('cautotest')
        global_config.global_config.get_config_value(
                'CROS', 'lab_status_url').AndReturn(_FAKE_URL)
        site_utils._get_lab_status(_FAKE_URL).AndReturn(None)


    def _setup_lab_status(self, json_string):
        """Set up to mock a given lab status.

        @param json_string JSON string for the JSON object to return
                           from `_get_lab_status()`.

        """
        global_config.global_config.get_config_value(
                'SERVER', 'hostname').AndReturn('cautotest')
        global_config.global_config.get_config_value(
                'CROS', 'lab_status_url').AndReturn(_FAKE_URL)
        json_value = json.loads(json_string)
        site_utils._get_lab_status(_FAKE_URL).AndReturn(json_value)


    def _try_check_no_board(self):
        """Test calling check_lab_status() with no board."""
        try:
            self.mox.ReplayAll()
            site_utils.check_lab_status()
        finally:
            self.mox.VerifyAll()


    def _try_check_dead_board(self):
        """Test calling check_lab_status() with 'deadboard'."""
        try:
            self.mox.ReplayAll()
            site_utils.check_lab_status('deadboard')
        finally:
            self.mox.VerifyAll()


    def _try_check_live_board(self):
        """Test calling check_lab_status() with 'liveboard'."""
        try:
            self.mox.ReplayAll()
            site_utils.check_lab_status('liveboard')
        finally:
            self.mox.VerifyAll()


    def test_non_cautotest_no_board(self):
        """Test a call with no board when the host isn't cautotest."""
        self._setup_not_cautotest()
        self._try_check_no_board()


    def test_non_cautotest_with_board(self):
        """Test a call with a board when the host isn't cautotest."""
        self._setup_not_cautotest()
        self._try_check_live_board()


    def test_no_status_no_board(self):
        """Test without a board when `_get_lab_status()` returns `None`."""
        self._setup_no_status()
        self._try_check_no_board()


    def test_no_lab_status_with_board(self):
        """Test with a board when `_get_lab_status()` returns `None`."""
        self._setup_no_status()
        self._try_check_live_board()


    def test_lab_up_no_board(self):
        """Test lab open with no board specified."""
        self._setup_lab_status(_OPEN_STATUS_VALUES[0])
        self._try_check_no_board()


    def test_lab_up_live_board(self):
        """Test lab open with a board specified."""
        self._setup_lab_status(_OPEN_STATUS_VALUES[0])
        self._try_check_live_board()


    def test_lab_down_no_board(self):
        """Test lab closed with no board specified."""
        self._setup_lab_status(_CLOSED_STATUS_VALUES[0])
        with self.assertRaises(site_utils.LabIsDownException):
            self._try_check_no_board()


    def test_lab_down_live_board(self):
        """Test lab closed with a board specified."""
        self._setup_lab_status(_CLOSED_STATUS_VALUES[0])
        with self.assertRaises(site_utils.LabIsDownException):
            self._try_check_live_board()


    def test_board_disabled_no_board(self):
        """Test board disabled with no board specified."""
        self._setup_lab_status(_DEADBOARD_STATUS_VALUES[0])
        self._try_check_no_board()


    def test_board_disabled_live_board(self):
        """Test board disabled with a live board specified."""
        self._setup_lab_status(_DEADBOARD_STATUS_VALUES[0])
        self._try_check_live_board()


    def test_board_disabled_dead_board(self):
        """Test board disabled with the disabled board specified."""
        self._setup_lab_status(_DEADBOARD_STATUS_VALUES[0])
        with self.assertRaises(site_utils.BoardIsDisabledException):
            self._try_check_dead_board()


if __name__ == '__main__':
    unittest.main()
