# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

import expectation_checker


class perf_expectation_checker_test(unittest.TestCase):
    def test__init__(self):
        checker = expectation_checker.perf_expectation_checker(
            'desktopui_PyAutoPerfTests','stumpy',
            'perf_expectations_test.json')
        expected = {
            'stumpy/desktopui_PyAutoPerfTests/milliseconds_NewTabCalendar':
            {'improve': '1230.000000',
             'regress': '1248.000000',
             'better':'lower'},
            'stumpy/desktopui_PyAutoPerfTests/milliseconds_NewTabCalendar':
            {'improve': '870.000000',
             'regress': '880.000000',
             'better':'lower'},
            'stumpy/test_1/higher_is_better_trace':
            {'improve': '200.0', 'regress': '100.0', 'better':'higher'},
            'stumpy/test_1/lower_is_better_trace':
            {'improve': '100.0', 'regress': '200.0', 'better':'lower'},
        }
        self.assertEqual(checker._expectations, expected)

    def test_compare_one_trace_lower_is_better(self):
        checker = expectation_checker.perf_expectation_checker(
            'test_1', 'stumpy',
            'perf_expectations_test.json')
        result = checker.compare_one_trace('lower_is_better_trace', 300.0)
        self.assertEqual(result, ('regress', 0.5))
        result = checker.compare_one_trace('lower_is_better_trace', 50.0)
        self.assertEqual(result, ('improve', 0.5))
        result = checker.compare_one_trace('lower_is_better_trace', 150.0)
        self.assertEqual(result, ('accept', None))

    def test_compare_one_trace_higher_is_better(self):
        checker = expectation_checker.perf_expectation_checker(
            'test_1', 'stumpy',
            'perf_expectations_test.json')
        result = checker.compare_one_trace('higher_is_better_trace', 50.0)
        self.assertEqual(result, ('regress', 0.5))
        result = checker.compare_one_trace('higher_is_better_trace', 300.0)
        self.assertEqual(result, ('improve', 0.5))
        result = checker.compare_one_trace('higher_is_better_trace', 150.0)
        self.assertEqual(result, ('accept', None))

    def test_compare_multiple_traces(self):

        checker = expectation_checker.perf_expectation_checker(
            'test_1', 'stumpy',
            'perf_expectations_test.json')
        perf_results = {
            'lower_is_better_trace': 50,
            'higher_is_better_trace': 50,
            }
        result = checker.compare_multiple_traces(perf_results)
        expected = {
            'improve': [('lower_is_better_trace', 0.5)],
            'regress': [('higher_is_better_trace', 0.5)],
            'accept': []}
        self.assertEqual(result, expected)


if __name__ == '__main__':
    logging.basicConfig(format='[%(levelname)s] %(message)s',
                        level=logging.DEBUG)
    unittest.main()
