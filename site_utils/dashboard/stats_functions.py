# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions called to analyze perf data for regressions."""

import logging

import external.stats as stats

from dash_view import AutotestDashView


class StatsFunctions(object):
  """Class to contain and invoke statistics functions."""

  def __init__(self):
    self._dash_view = AutotestDashView()

  def Invoke(self, function_name, params, vals, build):
    """Dispatch function and return True if failed."""
    if not hasattr(self, function_name):
      logging.debug('Stats function %s not found.', function_name)
      return False
    if build not in vals:
      logging.debug('Build %s not found in vals %s.', build, vals.keys())
      return False
    return getattr(self, function_name)(params, vals, build)

  def _Averages(self, vals, build):
    """Calculate averages for one build and all days."""
    build_mean = 0.0
    build_nsamples = 0
    previous_mean = 0.0
    previous_nsamples = 0
    mean_list = []
    sum_nsamples = 0
    # Loop through each build with values.
    for seq in vals:
      value_list = vals[seq][0]
      mean_value = stats.lmean(value_list)
      if build == seq:
        build_mean = mean_value
        build_nsamples = len(value_list)
      else:
        mean_list.append(mean_value)
        sum_nsamples += len(value_list)
    # Average over all builds prior to and not including this build.
    if mean_list:
      historical_mean = stats.lmean(mean_list)
      historical_samples = sum_nsamples / len(mean_list)
    else:
      historical_mean = 0.0
      historical_samples = 0
    results = {
        'build_mean': build_mean,
        'build_samples': build_nsamples,
        'historical_mean': historical_mean,
        'historical_samples': historical_samples}
    return results

  def PrintAverages(self, params, vals, build):
    """Always returns True - for regular summaries."""
    data_statistics = self._Averages(vals, build)
    return True, data_statistics

  def PrintStats(self, params, vals, build):
    """Always returns True - for detailed summaries."""
    value_list = vals[build][0]
    stats_lstdev = 0.0
    stats_lmed = value_list[0]
    if len(value_list) > 1:
      stats_lstdev = stats.lstdev(value_list)
      stats_lmed = stats.lmedianscore(value_list)
    # This is a 'sample standard deviation'.
    data_statistics = {
        'build_sample_stdev': stats_lstdev,
        'build_median_value': stats_lmed}
    return True, data_statistics

  def PrintHistogram(self, params, vals, build):
    """Always returns True - for detailed summaries."""
    numbins = params['numbins']
    limits = params['limits']
    bins, lowbin, binsize, lowpoints, highpoints = stats.lhistogram(
        vals[build][0], numbins, limits)
    data_array = []
    if lowpoints:
      data_array.append((lowpoints, 0, round(lowbin, 2)))
    for i in xrange(len(bins)):
      data_array.append((
          bins[i],
          round(lowbin+(binsize*i), 2),
          round(lowbin+(binsize*i)+binsize, 2)))
    if highpoints:
      data_array.append((highpoints, lowbin+binsize*len(bins), '...'))
    data_statistics = {
        'histogram': {
            'data': data_array,
            'height': params['height'],
            'width': params['width']}}
    return True, data_statistics

  def PrintIterations(self, params, vals, build):
    """Always returns True - for detailed summaries."""
    value_list = vals[build][0]
    test_idxes = vals[build][1]
    if len(value_list) <= 1:
      return False, {}
    iterations = vals[build][2]
    list_len = len(value_list)
    if not list_len == len(iterations):
      logging.warning('KeyVals without matching iterations on build %s.', build)
      return False, {}
    previous_iteration = 0  # Autotest iterations are 1-based.
    i = 1
    column_array = [(
        vals[build][3][0],
        self._dash_view.GetTestFromIdx(test_idxes[0])['tag'])]
    value_array = []
    known_iterations = set()
    for j in xrange(list_len):
      iteration = iterations[j]
      value = value_list[j]
      if iteration <= previous_iteration:
        i += 1
        column_array.append((
            vals[build][3][j],
            self._dash_view.GetTestFromIdx(test_idxes[j])['tag']))
      if not iteration in known_iterations:
        value_array.append((iteration-1, 0, iteration))
        known_iterations.add(iteration)
      value_array.append((iteration-1, i, value))
      previous_iteration = iteration
    data_statistics =  {
        'values': {
            'column_names': column_array,
            'rowcount': len(known_iterations),
            'data': value_array,
            'height': params['height'],
            'width': params['width']}}
    return True, data_statistics

  def OverAverage(self, params, vals, build):
    """Returns True if build average is > overall average."""
    data_statistics = self._Averages(vals, build)
    build_avg, _, overall_avg, _ = data_statistics
    return build_avg > overall_avg, data_statistics

  def OverThreshhold(self, params, vals, build):
    """Returns True if latest build is > threshhold."""
    data_statistics = self._Averages(vals, build)
    build_avg, _, _, _ = data_statistics
    return build_avg > float(params), data_statistics

  def UnderThreshhold(self, params, vals, build):
    """Returns True if latest build is < threshhold."""
    data_statistics = self._Averages(vals, build)
    build_avg, _, _, _ = data_statistics
    return build_avg < float(params), data_statistics
