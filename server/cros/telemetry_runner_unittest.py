#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/telemetry_runner.py."""
import mox

import common
from autotest_lib.server.cros import telemetry_runner


class TelemetryResultTest(mox.MoxTestBase):
    """Unit tests for telemetry_runner.TelemetryResult."""


    def testEmptyStdout(self):
        """Test when the test exits with 0 but there is no output."""
        result = telemetry_runner.TelemetryResult()
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.FAILED_STATUS)


    def testOnlyCSV(self):
        """Test when the stdout is only CSV format."""
        stdout = ('url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n')
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=0, stdout=stdout)
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.SUCCESS_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testOnlyCSVWithWarnings(self):
        """Test when the stderr has Warnings."""
        stdout = ('url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n')
        stderr = ('WARNING: Page failed to load http://www.facebook.com\n'
                  'WARNING: Page failed to load http://www.yahoo.com\n')
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=2, stdout=stdout,
                                                  stderr=stderr)
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.WARNING_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testOnlyCSVWithWarningsAndTraceback(self):
        """Test when the stderr has Warnings and Traceback."""
        stdout = ('url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n')
        stderr = ('WARNING: Page failed to load http://www.facebook.com\n'
                  'WARNING: Page failed to load http://www.yahoo.com\n'
                  'Traceback (most recent call last):\n'
                  'File "../../utils/unittest_suite.py", line 238, in '
                  '<module>\n'
                  'main()')
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=2, stdout=stdout,
                                                  stderr=stderr)
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.FAILED_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testInfoBeforeCSV(self):
        """Test when there is info before the CSV format."""
        stdout = ('Pages: [http://www.google.com, http://www.facebook.com]\n'
                  'url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n')
        stderr = 'WARNING: Page failed to load http://www.facebook.com\n'
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=1, stdout=stdout,
                                                  stderr=stderr)
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.WARNING_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testInfoAfterCSV(self):
        """Test when there is info after the CSV format."""
        stdout = ('url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n'
                  'RESULT load_time for http://www.google.com = 5\n'
                  'RESULT image_decode_time for http://www.google.com = 100\n'
                  'RESULT image_count for http://www.google.com = 10\n')
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=0, stdout=stdout,
                                                  stderr='')
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.SUCCESS_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testInfoBeforeAndAfterCSV(self):
        """Test when there is info before and after CSV format."""
        stdout = ('Pages: [http://www.google.com]\n'
                  'url,load_time (ms),image_decode_time (ms),image_count '
                  '(count)\n'
                  'http://www.google.com,5,100,10\n'
                  'RESULT load_time for http://www.google.com = 5\n'
                  'RESULT image_decode_time for http://www.google.com = 100\n'
                  'RESULT image_count for http://www.google.com = 10\n')
        expected_keyvals = {
                'load_time_ms-http___www.google.com': '5',
                'image_decode_time_ms-http___www.google.com': '100',
                'image_count-http___www.google.com':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=0, stdout=stdout,
                                                  stderr='')
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.SUCCESS_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testNoCSV(self):
        """Test when CSV format is missing from stdout."""
        stdout = ('Pages: [http://www.google.com]\n'
                  'RESULT load_time for http://www.google.com = 5\n'
                  'RESULT image_decode_time for http://www.google.com = 100\n'
                  'RESULT image_count for http://www.google.com = 10)\n')
        expected_keyvals = {}

        result = telemetry_runner.TelemetryResult(exit_code=0, stdout=stdout,
                                                  stderr='')
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.SUCCESS_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testBadCharactersInUrlAndValues(self):
        """Test that bad characters are cleaned up in value names and urls."""
        stdout = ('url,load_time (ms),image_decode_time?=% (ms),image_count '
                  '(count)\n'
                  'http://www.google.com?search=&^@$You,5,100,10\n')
        expected_keyvals = {
                'load_time_ms-http___www.google.com_search_____You': '5',
                'image_decode_time____ms-http___www.google.com_search_____You':
                '100',
                'image_count-http___www.google.com_search_____You':'10'}

        result = telemetry_runner.TelemetryResult(exit_code=0, stdout=stdout,
                                                  stderr='')
        result.parse_benchmark_results()
        self.assertEquals(result.status, telemetry_runner.SUCCESS_STATUS)
        self.assertEquals(expected_keyvals, result.perf_keyvals)


    def testCleanupUnits(self):
        """Test that weird units are cleaned up."""
        result = telemetry_runner.TelemetryResult()
        self.assertEquals(result._cleanup_value('loadtime (ms)'),
                                                'loadtime_ms')
        self.assertEquals(result._cleanup_value('image_count ()'),
                                                'image_count')
        self.assertEquals(result._cleanup_value('image_count (count)'),
                                                'image_count')
        self.assertEquals(result._cleanup_value(
                'CodeLoad (score (bigger is better))'),
                'CodeLoad_score')
        self.assertEquals(result._cleanup_value('load (%)'),
                                                'load_percent')
        self.assertEquals(result._cleanup_value('load_percent (%)'),
                                                'load_percent')
        self.assertEquals(result._cleanup_value('score (runs/s)'),
                                                'score_runs_per_s')