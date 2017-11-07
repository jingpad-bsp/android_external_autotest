from autotest_lib.client.bin import utils

class SystemMetricsCollector(object):
    """
    Collects system metrics.
    """
    def __init__(self):
        self.metrics = [MemUsageMetric(),
                        CpuUsageMetric(),
                        AllocatedFileHandlesMetric()]

    def collect_snapshot(self):
        """
        Collects one snapshot of metrics.
        """
        for metric in self.metrics:
            metric.collect_metric()

    def write_metrics(self, writer_function):
        """
        Writes the collected metrics using the specified writer function.

        @param writer_function: A function with the following signature:
                 f(description, value, units, higher_is_better)
        """
        for metric in self.metrics:
            writer_function(
                    metric.description,
                    metric.values,
                    units=metric.units,
                    higher_is_better=metric.higher_is_better)

class Metric(object):
    """Abstract base class for metrics."""
    def __init__(self, description, units=None, higher_is_better=False):
        """
        Initializes a Metric.
        @param description: Description of the metric, e.g., used as label on a
                dashboard chart
        @param units: Units of the metric, e.g. percent, seconds, MB.
        @param higher_is_better: Whether a higher value is considered better or
                not.
        """
        self.values = []
        self.description = description
        self.units = units
        self.higher_is_better = higher_is_better

    def collect_metric(self):
        """
        Collects one metric.
        """
        raise NotImplementedError('Subclasses should override')

class MemUsageMetric(Metric):
    """
    Metric that collects memory usage in percent.

    Memory usage is collected in percent. Buffers and cached are calculated
    as free memory.
    """
    def __init__(self):
        super(MemUsageMetric, self).__init__('memory_usage', units='percent')

    def collect_metric(self):
        total_memory = utils.get_mem_total()
        free_memory = utils.get_mem_free_plus_buffers_and_cached()
        used_memory = total_memory - free_memory
        usage_percent = (used_memory * 100) / total_memory
        self.values.append(usage_percent)

class CpuUsageMetric(Metric):
    """
    Metric that collects cpu usage in percent.
    """
    def __init__(self):
        super(CpuUsageMetric, self).__init__('cpu_usage', units='percent')
        self.last_usage = None


    def collect_metric(self):
        """
        Collects CPU usage in percent.

        Since the CPU active time we query is a cumulative metric, the first
        collection does not actually save a value. It saves the first value to
        be used for subsequent deltas.
        """
        current_usage = utils.get_cpu_usage()
        if self.last_usage is not None:
            # Compute the percent of active time since the last update to
            # current_usage.
            usage_percent = 100 * utils.compute_active_cpu_time(
                    self.last_usage, current_usage)
            self.values.append(usage_percent)
        self.last_usage = current_usage

class AllocatedFileHandlesMetric(Metric):
    """
    Metric that collects the number of allocated file handles.
    """
    def __init__(self):
        super(AllocatedFileHandlesMetric, self).__init__(
                'allocated_file_handles', units='handles')

    def collect_metric(self):
        self.values.append(utils.get_num_allocated_file_handles())

