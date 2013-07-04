# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module handling the logs.

The structure of this module:

    RoundLog: the test results of every round are saved in a log file.
              includes: fw, and round_name (i.e., the date time of the round

      --> GestureLogs: includes gesture name, and variation

            --> ValidatorLogs: includes name, details, criteria, score, metrics


    SummaryLog: derived from multiple RoundLogs
      --> SimpleTable: (key, vlog) pairs
            key: (fw, round_name, gesture_name, variation_name, validator_name)
            vlog: name, details, criteria, score, metrics

    TestResult: encapsulation of scores and metrics
                used by a client program to query the test results
      --> StatisticsScores: includes average, ssd, and count
      --> StatisticsMetrics: includes average, min, max, and more


How the logs work:
    (1) ValidatorLogs are contained in a GestureLog.
    (2) Multiple GestureLogs are packed in a RoundLog which is saved in a
        separate pickle log file.
    (3) To construct a SummaryLog, it reads RoundLogs from all pickle logs
        in the specified log directory. It then creates a SimpleTable
        consisting of (key, ValidatorLog) pairs, where
        key is a 5-tuple:
            (fw, round_name, gesture_name, variation_name, validator_name).
    (4) The client program, i.e., firmware_summary module, contains a
        SummaryLog, and queries all statistics using get_result() which returns
        a TestResult object containing both StatisticsScores and
        StatisticsMetrics.

"""


import glob
import numpy as n
import pickle
import os

import test_conf as conf
import validators as val

from collections import defaultdict, namedtuple
from sets import Set

from common_util import Debug, print_and_exit
from firmware_constants import AXIS


MetricProps = namedtuple('MetricProps', ['description', 'stat_func'])


def _setup_debug(debug_flag):
    """Set up the global debug_print function."""
    if 'debug_print' not in globals():
        global debug_print
        debug = Debug(debug_flag)
        debug_print = debug.print_msg


def _calc_sample_standard_deviation(sample):
    """Calculate the sample standard deviation (ssd) from a given sample.

    To compute a sample standard deviation, the following formula is used:
        sqrt(sum((x_i - x_average)^2) / N-1)

    Note that N-1 is used in the denominator for sample standard deviation,
    where N-1 is the degree of freedom. We need to set ddof=1 below;
    otherwise, N would be used in the denominator as ddof's default value
    is 0.

    Reference:
        http://en.wikipedia.org/wiki/Standard_deviation
    """
    return n.std(n.array(sample), ddof=1)


class Metric:
    """A class to handle the name and the value of a metric."""
    def __init__(self, name, value):
        self.name = name
        self.value = value


class MetricNameProps:
    """A class keeping the information of metric name templates, descriptions,
    and statistic functions.
    """

    def __init__(self):
        self._init_raw_metrics_props()
        self._derive_metrics_props()

    @staticmethod
    def get_report_interval(report_rate):
        """Convert the report rate in Hz to report interval in ms.

        @param report_rate: the report rate in Hz
        Return: the report interval in ms
        """
        return '%.2f' % (1.0 / report_rate * 1000)

    def _init_raw_metrics_props(self):
        """Initialize raw_metrics_props.

        The raw_metrics_props is a dictionary from metric attribute to the
        corresponding metric properties. Take MAX_ERR as an example of metric
        attribute. Its metric properties include
          . metric name template: 'max error in {} (mm)'
            The metric name template will be expanded later. For example,
            with name variations ['x', 'y'], the above template will be
            expanded to:
                'max error in x (mm)', and
                'max error in y (mm)'
          . name variations: for example, ['x', 'y'] for MAX_ERR
          . metric name description: 'The max err of all samples'
          . the stat function used to calculate the statistics for the metric:
            we use max() to calculate MAX_ERR in x/y for linearity.
        """
        # stat_functions may include: max, min, average, and pct
        average = lambda lst: float(sum(lst)) / len(lst)
        _pct = lambda lst: float(lst[0]) / lst[1] * 100
        pct = lambda lst: _pct([sum(count) for count in zip(*lst)])

        max_report_interval_str = self.get_report_interval(conf.min_report_rate)

        # A dictionary from metric attribute to its properties:
        #    {metric_attr: (template, name_variations, description, stat_func)}
        self.raw_metrics_props = {
            # Linearity Validator
            'MAX_ERR': (
                'max error in {} (mm)',
                AXIS.LIST,
                'The max err of all samples',
                max),
            'RMS_ERR': (
                'rms error in {} (mm)',
                AXIS.LIST,
                'The mean of all rms means of all trials',
                average),
            # Range Validator
            'RANGE': (
                '{} edge not reached (mm)',
                ['left', 'right', 'top', 'bottom'],
                'Min unreachable distance',
                max),
            # Stationary Finger Validator
            'MAX_DISTANCE': (
                'max distance (mm)',
                None,
                'max distance of any two points from any run',
                max),
            # Physical Click Validator
            'CLICK': (
                '{}f-click miss rate (%)',
                [1, 2, 3, 4, 5],
                'Should be close to 0 (0 is perfect)',
                pct),
            # Drumroll Validator
            'CIRCLE_RADIUS': (
                'circle radius (mm)',
                None,
                'Anything over 2mm is failure',
                max),
            # Report Rate Validator
            'LONG_INTERVALS': (
                'intervals > {} ms (%)',
                [max_report_interval_str,],
                '0% is required',
                pct),
            'AVE_TIME_INTERVAL': (
                'average time interval (ms)',
                None,
                'less than %s ms is required' % max_report_interval_str,
                average),
            'MAX_TIME_INTERVAL': (
                'max time interval (ms)',
                None,
                'less than %s ms is required' % max_report_interval_str,
                max),
        }

        # Set the metric attribute to its template
        #   E.g., self.MAX_ERR = 'max error in {} (mm)'
        for key, (template, _, _, _) in self.raw_metrics_props.items():
            setattr(self, key, template)

    def _derive_metrics_props(self):
        """Expand the metric name templates to the metric names, and then
        derive the expanded metrics_props.

        In _init_raw_metrics_props():
            The raw_metrics_props is defined as:
                'MAX_ERR': (
                    'max error in {} (mm)',             # template
                    ['x', 'y'],                         # name variations
                    'The max err of all samples',       # description
                    max),                               # stat_func
                ...

            By expanding the template with its corresponding name variations,
            the names related with MAX_ERR will be:
                'max error in x (mm)', and
                'max error in y (mm)'

        Here we are going to derive metrics_props as:
                metrics_props = {
                    'max error in x (mm)':
                        MetricProps('The max err of all samples', max),
                    ...
                }
        """
        self.metrics_props = {}
        for raw_props in self.raw_metrics_props.values():
            template, name_variations, description, stat_func = raw_props
            metric_props = MetricProps(description, stat_func)
            if name_variations:
                # Expand the template with every variations.
                #   E.g., template = 'max error in {} (mm)' is expanded to
                #         name = 'max error in x (mm)'
                for variation in name_variations:
                    name = template.format(variation)
                    self.metrics_props[name] = metric_props
            else:
                # Otherwise, the template is already the name.
                #   E.g., the template 'max distance (mm)' is same as the name.
                self.metrics_props[template] = metric_props


class ValidatorLog:
    """A class handling the logs reported by validators."""
    def __init__(self):
        self.name = None
        self.details = []
        self.criteria = None
        self.score = None
        self.metrics = []
        self.error = None

    def reset(self):
        """Reset all attributes."""
        self.details = []
        self.score = None
        self.metrics = []
        self.error = None

    def insert_details(self, msg):
        """Insert a msg into the details."""
        self.details.append(msg)


class GestureLog:
    """A class handling the logs related with a gesture."""
    def __init__(self):
        self.name = None
        self.variation = None
        self.prompt = None
        self.vlogs = []


class RoundLog:
    """Manipulate the test result log generated in a single round."""
    def __init__(self, fw=None, round_name=None):
        self._fw = fw
        self._round_name = round_name
        self._glogs = []

    def dump(self, filename):
        """Dump the log to the specified filename."""
        try:
            with open(filename, 'w') as log_file:
                pickle.dump([self._fw, self._round_name, self._glogs], log_file)
        except Exception, e:
            msg = 'Error in dumping to the log file (%s): %s' % (filename, e)
            print_and_exit(msg)

    @staticmethod
    def load(filename):
        """Load the log from the pickle file."""
        try:
            with open(filename) as log_file:
                return pickle.load(log_file)
        except Exception, e:
            msg = 'Error in loading the log file (%s): %s' % (filename, e)
            print_and_exit(msg)

    def insert_glog(self, glog):
        """Insert the gesture log into the round log."""
        if glog.vlogs:
            self._glogs.append(glog)


class StatisticsScores:
    """A statistics class to compute the average, ssd, and count of
    aggregate scores.
    """
    def __init__(self, scores):
        self.all_data = ()
        if scores:
            self.average = n.average(n.array(scores))
            self.ssd = _calc_sample_standard_deviation(scores)
            self.count = len(scores)
            self.all_data = (self.average, self.ssd, self.count)


class StatisticsMetrics:
    """A statistics class to compute the statistics including the min, max, or
    average of aggregate metrics.
    """

    def __init__(self, metrics):
        """Collect all values for every metric.

        @param metrics: a list of Metric objects.
        """
        # metrics_values: the raw metrics values
        self.metrics_values = defaultdict(list)
        for metric in metrics:
            self.metrics_values[metric.name].append(metric.value)

        # Calculate the statistics of metrics using corresponding stat functions
        self._calc_statistics(MetricNameProps().metrics_props)

    def _calc_statistics(self, metrics_props):
        """Calculate the desired statistics for every metric.

        @param metrics_props: a dictionary mapping a metric name to a
                metric props including the description and stat_func
        """
        self.metrics_props = metrics_props
        self.stats_values = {}
        for metric_name, values in self.metrics_values.items():
            assert metric_name in metrics_props
            stat_func = metrics_props[metric_name].stat_func
            self.stats_values[metric_name] = stat_func(values)


class TestResult:
    """A class includes the statistics of the score and the metrics."""
    def __init__(self, scores, metrics):
        self.stat_scores = StatisticsScores(scores)
        self.stat_metrics = StatisticsMetrics(metrics)


class SimpleTable:
    """A very simple data table."""
    def __init__(self):
        self._table = {}

    def insert(self, key, value):
        """Insert a row. If the key exists already, the value is appended."""
        if self._table.get(key) is None:
            self._table[key] = []
        self._table[key].append(value)
        debug_print('    key: %s' % str(key))

    def search(self, key):
        """Search rows with the specified key.

        A key is a list of attributes.
        If any attribute is None, it means no need to match this attribute.
        """
        match = lambda i, j: i == j or j is None
        return filter(lambda (k, vlog): all(map(match, k, key)),
                      self._table.items())

    def items(self):
        """Return the table items."""
        return self._table.items()


class SummaryLog:
    """A class to manipulate the summary logs.

    A summary log may consist of result logs of different firmware versions
    where every firmware version may consist of multiple rounds.
    """
    def __init__(self, log_dir, segment_weights, validator_weights, debug_flag):
        self.log_dir = log_dir
        self.segment_weights = segment_weights
        self.validator_weights = validator_weights
        _setup_debug(debug_flag)
        self._read_logs()
        self.ext_validator_weights = self._compute_extended_validator_weight(
                self.validators)

    def _get_firmware_version(self, filename):
        """Get the firmware version from the given filename."""
        return filename.split('-')[2]

    def _read_logs(self):
        """Read the result logs in the specified log directory."""
        # Get logs in the log_dir or its sub-directories.
        log_filenames = glob.glob(os.path.join(self.log_dir, '*.log'))
        if not log_filenames:
            log_filenames = glob.glob(os.path.join(self.log_dir, '*', '*.log'))

        if not log_filenames:
            err_msg = 'Error: no log files in the test result directory: %s'
            print_and_exit(err_msg % self.log_dir)

        self.log_table = SimpleTable()
        self.fws = Set()
        self.gestures = Set()
        self.validators = Set()
        for log_filename in log_filenames:
            self._add_round_log(log_filename)

        self.fws = sorted(list(self.fws))
        self.gestures = sorted(list(self.gestures))
        self.validators = sorted(list(self.validators))

    def _add_round_log(self, log_filename):
        """Add the round log, decompose the validator logs, and build
        a flat summary log.
        """
        fw, round_name, glogs = RoundLog.load(log_filename)
        self.fws.add(fw)
        debug_print('  fw(%s) round(%s)' % (fw, round_name))
        # Iterate through every gesture_variation of the round log,
        # and generate a flat dictionary of the validator logs.
        for glog in glogs:
            self.gestures.add(glog.name)
            for vlog in glog.vlogs:
                self.validators.add(vlog.name)
                key = (fw, round_name, glog.name, glog.variation, vlog.name)
                self.log_table.insert(key, vlog)

    def _compute_extended_validator_weight(self, validators):
        """Compute extended validator weight from validator weight and segment
        weight. The purpose is to merge the weights of split validators, e.g.
        Linearity(*)Validator, so that their weights are not counted multiple
        times.

        Example:
          validators = ['CountTrackingIDValidator',
                        'Linearity(BothEnds)Validator',
                        'Linearity(Middle)Validator',
                        'NoGapValidator']

          Note that both names of the validators
                'Linearity(BothEnds)Validator' and
                'Linearity(Middle)Validator'
          are created at run time from LinearityValidator and use
          the relative weights defined by segment_weights.

          validator_weights = {'CountTrackingIDValidator': 12,
                               'LinearityValidator': 10,
                               'NoGapValidator': 10}

          segment_weights = {'Middle': 0.7,
                             'BothEnds': 0.3}

          split_validator = {'Linearity': ['BothEnds', 'Middle'],}

          adjusted_weight of Lineary(*)Validator:
            Linearity(BothEnds)Validator = 0.3 / (0.3 + 0.7) * 10 = 3
            Linearity(Middle)Validator =   0.7 / (0.3 + 0.7) * 10 = 7

          extended_validator_weights: {'CountTrackingIDValidator': 12,
                                       'Linearity(BothEnds)Validator': 3,
                                       'Linearity(Middle)Validator': 7,
                                       'NoGapValidator': 10}
        """
        extended_validator_weights = {}
        split_validator = {}

        # Copy the base validator weight into extended_validator_weights.
        # For the split validators, collect them in split_validator.
        for v in validators:
            base_name, segment = val.get_base_name_and_segment(v)
            if segment is None:
                # It is a base validator. Just copy it into the
                # extended_validaotr_weight dict.
                extended_validator_weights[v] = self.validator_weights[v]
            else:
                # It is a derived validator, e.g., Linearity(BothEnds)Validator
                # Needs to compute its adjusted weight.

                # Initialize the split_validator for this base_name if not yet.
                if split_validator.get(base_name) is None:
                    split_validator[base_name] = []

                # Append this segment name so that we know all segments for
                # the base_name.
                split_validator[base_name].append(segment)

        # Compute the adjusted weight for split_validator
        for base_name in split_validator:
            name = val.get_validator_name(base_name)
            weight_list = [self.segment_weights[segment]
                           for segment in split_validator[base_name]]
            weight_sum = sum(weight_list)
            for segment in split_validator[base_name]:
                derived_name = val.get_derived_name(name, segment)
                adjusted_weight = (self.segment_weights[segment] / weight_sum *
                                   self.validator_weights[name])
                extended_validator_weights[derived_name] = adjusted_weight

        return extended_validator_weights

    def get_result(self, fw=None, round=None, gesture=None, variation=None,
                   validator=None):
        """Get the result statistics of a validator which include both
        the score and the metrics.
        """
        key = (fw, round, gesture, variation, validator)
        rows = self.log_table.search(key)
        scores = [vlog.score for _key, vlogs in rows for vlog in vlogs]
        metrics = [metric for _key, vlogs in rows
                              for vlog in vlogs
                                  for metric in vlog.metrics]
        return TestResult(scores, metrics)

    def get_final_weighted_average(self):
        """Calculate the final weighted average."""
        weighted_average = {}
        for fw in self.fws:
            scores = [self.get_result(fw=fw,
                                      validator=validator).stat_scores.average
                      for validator in self.validators]
            _, weights = zip(*sorted(self.ext_validator_weights.items()))
            weighted_average[fw] = n.average(scores, weights=weights)
        return weighted_average
