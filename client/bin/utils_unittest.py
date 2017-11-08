#!/usr/bin/python

__author__ = "kerl@google.com, gwendal@google.com (Gwendal Grignou)"

import io
import unittest

from autotest_lib.client.bin import utils

class TestUtils(unittest.TestCase):
    """Test utils functions."""

    # Test methods, disable missing-docstring
    # pylint: disable=missing-docstring
    def setUp(self):
        utils._open_file = self.fake_open
        # Files opened with utils._open_file will contain this string.
        self.fake_file_text = ''

    def fake_open(self, path):
        # Use BytesIO instead of StringIO to support with statements.
        return io.BytesIO(bytes(self.fake_file_text))

    def test_concat_partition(self):
        self.assertEquals("nvme0n1p3", utils.concat_partition("nvme0n1", 3))
        self.assertEquals("mmcblk1p3", utils.concat_partition("mmcblk1", 3))
        self.assertEquals("sda3", utils.concat_partition("sda", 3))

    # The columns in /proc/stat are:
    # user nice system idle iowait irq softirq steal guest guest_nice
    #
    # Although older kernel versions might not contain all of them.
    # Unit is 1/100ths of a second.
    def test_get_cpu_usage(self):
        self.fake_file_text = 'cpu 254544 9 254768 2859878\n'
        usage = utils.get_cpu_usage()
        self.assertEquals({
            'user': 254544,
            'nice': 9,
            'system': 254768,
            'idle': 2859878,
        }, usage)

    def test_compute_active_cpu_time(self):
        start_usage = {
            'user': 900,
            'nice': 10,
            'system': 90,
            'idle': 10000,
        }
        end_usage = {
            'user': 1800,
            'nice': 20,
            'system': 180,
            'idle': 11000,
        }
        usage = utils.compute_active_cpu_time(start_usage, end_usage)
        self.assert_is_close(usage, 0.5)

    def test_compute_active_cpu_time_idle(self):
        start_usage = {
            'user': 900,
            'nice': 10,
            'system': 90,
            'idle': 10000,
        }
        end_usage = {
            'user': 900,
            'nice': 10,
            'system': 90,
            'idle': 11000,
        }
        usage = utils.compute_active_cpu_time(start_usage, end_usage)
        self.assert_is_close(usage, 0)

    def test_get_mem_total(self):
        self.fake_file_text = ('MemTotal:  2048000 kB\n'
                               'MemFree:  307200 kB\n'
                               'Buffers:  102400 kB\n'
                               'Cached:   204800 kB\n')
        self.assert_is_close(utils.get_mem_total(), 2000)

    def test_get_mem_free(self):
        self.fake_file_text = ('MemTotal:  2048000 kB\n'
                               'MemFree:  307200 kB\n'
                               'Buffers:  102400 kB\n'
                               'Cached:   204800 kB\n')
        self.assert_is_close(utils.get_mem_free(), 300)

    def test_get_mem_free_plus_buffers_and_cached(self):
        self.fake_file_text = ('MemTotal:  2048000 kB\n'
                               'MemFree:  307200 kB\n'
                               'Buffers:  102400 kB\n'
                               'Cached:   204800 kB\n')
        self.assert_is_close(utils.get_mem_free_plus_buffers_and_cached(), 600)

    def test_get_num_allocated_file_handles(self):
        self.fake_file_text = '123 0 456\n'
        self.assertEqual(utils.get_num_allocated_file_handles(), 123)

    def assert_is_close(self, a, b, allowed_delta = 0.0000001):
        """
        Asserts that two floats are within the allowed delta of each other.
        @param allowed_delta: The allowed delta between the two floats.
        """
        self.assertTrue(abs(a - b) < allowed_delta,
                        "%f and %f are not within %f of each other"
                                % (a, b, allowed_delta))

