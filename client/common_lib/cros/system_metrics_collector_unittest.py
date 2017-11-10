from autotest_lib.client.common_lib.cros import system_metrics_collector

import unittest

# pylint: disable=missing-docstring
class TestSystemMetricsCollector(unittest.TestCase):
    """
    Tests for the system_metrics_collector module.
    """
    def test_mem_usage_metric(self):
        metric = system_metrics_collector.MemUsageMetric(FakeSystemFacade())
        metric.collect_metric()
        self.assertAlmostEqual(60, metric.values[0])

    def test_file_handles_metric(self):
        metric = system_metrics_collector.AllocatedFileHandlesMetric(
                FakeSystemFacade())
        metric.collect_metric()
        self.assertEqual(11, metric.values[0])

    def test_cpu_usage_metric(self):
        metric = system_metrics_collector.CpuUsageMetric(FakeSystemFacade())
        # Collect twice since the first collection only sets the baseline for
        # the following diff calculations.
        metric.collect_metric()
        metric.collect_metric()
        self.assertAlmostEqual(40, metric.values[0])

    def test_collector(self):
        collector = system_metrics_collector.SystemMetricsCollector(
                FakeSystemFacade(), [TestMetric])
        collector.collect_snapshot()
        d = {}
        def _write_func(**kwargs):
            d.update(kwargs)
        collector.write_metrics(_write_func)
        self.assertEquals('test_description', d['description'])
        self.assertEquals([1], d['value'])
        self.assertEquals(False, d['higher_is_better'])
        self.assertEquals('test_unit', d['units'])

class FakeSystemFacade(object):
    def __init__(self):
        self.mem_total_mb = 1000.0
        self.mem_free_mb = 400.0
        self.file_handles = 11
        self.active_cpu_time = 0.4

    def get_mem_total(self):
        return self.mem_total_mb

    def get_mem_free_plus_buffers_and_cached(self):
        return self.mem_free_mb

    def get_num_allocated_file_handles(self):
        return self.file_handles

    def get_cpu_usage(self):
        return {}

    def compute_active_cpu_time(self, last_usage, current_usage):
        return self.active_cpu_time

class TestMetric(system_metrics_collector.Metric):
    def __init__(self, system_facade):
        super(TestMetric, self).__init__(
                system_facade, 'test_description', units='test_unit')

    def collect_metric(self):
        self.values.append(1)


