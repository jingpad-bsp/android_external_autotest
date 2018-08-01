#!/usr/bin/python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest

import common

from autotest_lib.client.cros.video import histogram_verifier
import mock


class HistogramVerifierTest(unittest.TestCase):
    """
    Tests histogram_verifier's module methods.
    """

    HISTOGRAM_TEXT_1 = '\n'.join([
        'Histogram: Media.Engagement.ScoreAtPlayback recorded 29 samples, '
        'mean = 44.8 (flags = 0x41)',
        '0   ------------------------------------O                             '
        '        (6 = 20.7%)',
        '1   ...',
        '5   ------O                                                           '
        '       (1 = 3.4%) {20.7%}',
        '6   ...',
        '10  ------O                                                           '
        '        (1 = 3.4%) {24.1%}',
        '11  ...',
        '15  ------------------O                                               '
        '        (3 = 10.3%) {27.6%}',
        '16  ------------------------------O                                   '
        '        (5 = 17.2%) {37.9%}',
        '17  ...',
        '89  ------------------------------------------------------------------'
        '------O (12 = 41.4%) {55.2%}',
        '90  ------O                                                           '
        '        (1 = 3.4%) {96.6%}',
        '91  ... '])


    def test_parse_histogram(self):
        """
        Tests parse_histogram().
        """
        self.assertDictEqual(
            {0: 6, 5: 1, 10: 1, 15: 3, 16: 5, 89: 12, 90: 1},
            histogram_verifier.parse_histogram(self.HISTOGRAM_TEXT_1))
        self.assertDictEqual({}, histogram_verifier.parse_histogram(''))

    def test_subtract_histogra(self):
        """
        Tests subtract_histogram().
        """
        self.assertDictEqual({}, histogram_verifier.subtract_histogram({}, {}))
        self.assertDictEqual(
            {0: 10},
            histogram_verifier.subtract_histogram({0: 10}, {}))
        self.assertDictEqual(
            {0: -10},
            histogram_verifier.subtract_histogram({}, {0: 10}))
        self.assertDictEqual(
            {0: 10},
            histogram_verifier.subtract_histogram({0: 10}, {}))
        self.assertDictEqual(
            {0: 1},
            histogram_verifier.subtract_histogram({0: 1, 15:4}, {0:0, 15:4}))


class HistogramDifferTest(unittest.TestCase):
    """
    Tests histogram_verifier.HistogramDiffer class.
    """

    HISTOGRAM_BEGIN = '\n'.join([
        'Histogram: Media.GpuVideoDecoderInitializeStatus recorded 3521 samples'
        ', mean = 2.7 (flags = 0x41)',
        '0   ------------------------------------------------------------------'
        '------O (2895 = 82.2%)',
        '1   ...',
        '15  ----------------O                                                 '
        '        (626 = 17.8%) {82.2%}',
        '16  ... '])

    HISTOGRAM_END = '\n'.join([
        'Histogram: Media.GpuVideoDecoderInitializeStatus recorded 3522 samples'
        ', mean = 2.7 (flags = 0x41)',
        '0   ------------------------------------------------------------------'
        '------O (2896 = 82.2%)',
        '1   ...',
        '15  ----------------O                                                 '
        '        (626 = 17.8%) {82.2%}',
        '16  ... '])

    HISTOGRAM_NAME = 'Media.GpuVideoDecoderInitializeStatus'

    def test_init(self):
        """
        Tests __init__().
        """
        differ = histogram_verifier.HistogramDiffer(None, self.HISTOGRAM_NAME,
                                                    begin=False)
        self.assertEqual(self.HISTOGRAM_NAME, differ.histogram_name)
        self.assertDictEqual({}, differ.begin_histogram)
        self.assertDictEqual({}, differ.end_histogram)

    def test_begin_end(self):
        """
        Tests HistogramDiffer's begin() and end().

        Mocks out HistogramDiffer.get_histogram() to simplify test.
        """

        differ = histogram_verifier.HistogramDiffer(None, self.HISTOGRAM_NAME,
                                                    begin=False)
        differ._get_histogram = mock.Mock(
            side_effect = [
                (histogram_verifier.parse_histogram(self.HISTOGRAM_BEGIN),
                 self.HISTOGRAM_BEGIN),
                (histogram_verifier.parse_histogram(self.HISTOGRAM_END),
                 self.HISTOGRAM_END)])
        differ.begin()
        self.assertDictEqual({0: 1}, differ.end())

    def test_histogram_unchange(self):
        """
        Tests HistogramDiffer with histogram unchanged.

        Expects no difference.
        """
        differ = histogram_verifier.HistogramDiffer(None, self.HISTOGRAM_NAME,
                                                    begin=False)
        differ._get_histogram = mock.Mock(
            side_effect = [
                (histogram_verifier.parse_histogram(self.HISTOGRAM_BEGIN),
                 self.HISTOGRAM_BEGIN),
                (histogram_verifier.parse_histogram(self.HISTOGRAM_BEGIN),
                 self.HISTOGRAM_BEGIN)])
        differ.begin()
        self.assertDictEqual({}, differ.end())


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    unittest.main()
