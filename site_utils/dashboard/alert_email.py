# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Analyze perf keyvals and email regressions."""

import logging
import os

from django.shortcuts import render_to_response

import dash_util

from common_email import EmailNotifier
from preprocess_functions import PreprocessFunctions
from stats_functions import StatsFunctions

# String resources.
from dash_strings import ALERT_CHECKED_PREFIX
from dash_strings import BUILD_PERFORMANCE_FILE
from dash_strings import DASHBOARD_MAIN
from dash_strings import PERFORMANCE_DIR
from dash_strings import PERFORMANCE_REGRESSED_EMAIL


class AlertEmailNotifier(EmailNotifier):
  """Class to check for keyval alerts (perf regressions) and send emails."""

  def __init__(self, base_dir, netbook, board_type,
               use_sheriffs, extra_emails, plot_options):
    super(AlertEmailNotifier, self).__init__(
        base_dir, netbook, board_type, use_sheriffs, extra_emails,
        ALERT_CHECKED_PREFIX, PERFORMANCE_DIR)
    self._regressed_tests = {}
    self._preprocessors = PreprocessFunctions()
    self._stats = StatsFunctions()
    self._plot_options = plot_options
    self._preprocessed = False
    self._float_converter = dash_util.HumanReadableFloat()

  def ExpandWildcardKeys(self, test_name, perf_checks):
    """Add keys to the check list using wildcard prefixes."""
    keyvals = self._dash_view.GetTestKeyVals(
        self._netbook, self._board_type, test_name)
    if not keyvals:
      return []
    expanded_checks = perf_checks.copy()
    key_list = sorted(expanded_checks.keys())
    for key_match in key_list:
      if key_match[-1] == '*':
        key_len = len(key_match) - 1
        check_dict = expanded_checks[key_match]
        for perf_key in keyvals:
          if perf_key[:key_len] == key_match[:key_len]:
            if not perf_key in expanded_checks:
              expanded_checks[perf_key] = check_dict
        del expanded_checks[key_match]
    return expanded_checks

  def InvokePreprocessor(self, function_name, params, keyvals, checks):
    self._preprocessed = True
    return self._preprocessors.Invoke(function_name, params, keyvals, checks)

  def PreProcess(self, items, preprocess_functions):
    """Hook to manipulate keyvals before entering emailer pipeline."""
    categories, test_name, perf_checks = items
    for fn_name, params in preprocess_functions:
      keyvals = self._dash_view.GetTestKeyVals(
          self._netbook, self._board_type, test_name)
      if keyvals:
        self.InvokePreprocessor(fn_name, params, keyvals, perf_checks)

  def PreprocessorHTML(self, test_name, regressed_key_details):
    results = ''
    if self._preprocessed:
      results = self._preprocessors.PreprocessorHTML(
          test_name, regressed_key_details)
    return results

  def IsPreprocessedKey(self, key):
    return self._preprocessors.IsPreprocessedKey(key)

  def InvokeStats(self, function_name, params, vals, build):
    return self._stats.Invoke(function_name, params, vals, build)

  def GetTestPath(self, test_name):
    _, test_path = self._dash_view.GetAutotestInfo(test_name)
    return test_path

  def GetPlotLink(self, test_name, key_name):
    """Dig through the plot config json to get plot filename for linking."""
    plot_file = None
    for plot_id, plot_definition in self._plot_options.iteritems():
      if test_name == plot_definition['test']:
        if key_name in plot_definition['keys']:
          plot_file = '%s%s' % (test_name, plot_id)
    return plot_file

  def CheckItems(self, items):
    """Iterate through test categories and send email for failed tests."""
    categories, test_name, perf_checks = items
    for category in categories:
      for build in self.GetBuilds(category):
        if not self.Checked(category, build):
          regressed_tests = self._regressed_tests.setdefault(build, {})
          for alert_key, alert_checks in perf_checks.iteritems():
            vals = self._dash_view.GetTestPerfVals(
                self._netbook, self._board_type, test_name, alert_key)
            if not vals:
              logging.debug(
                  'No keyvals found for configuration requested: '
                  '%s, %s, %s, %s.',
                  self._board_type, self._netbook, test_name, alert_key)
              continue
            if not build in vals:
              logging.debug(
                  'No keyval found for configuration requested and build: '
                  '%s, %s, %s, %s, %s.',
                  self._board_type, self._netbook, test_name, alert_key,
                  build)
              continue
            for fn_name, fn_params in alert_checks.iteritems():
              stats_result, stats_data = self.InvokeStats(
                  fn_name, fn_params, vals, build)
              if stats_result:
                regressed_keys = regressed_tests.setdefault(test_name, {})
                regressed_stats = regressed_keys.setdefault(alert_key, {})
                regressed_stats.update(stats_data)
          # Write the sentinel file
          self.SetChecked(category, build)

  def GenerateEmail(self):
    """Send email to aid troubleshooting performance regressions.

    Emails are broken into 3 or 4 sections:
    1. Intro with summary of failing build and netbook combination.
    2. An optional section of ui if preprocessing.
    3  A list of regressed keys, details and related plots inline.
    4. Inline build log for blame.
    """

    for tpl_build, regressed_tests in self._regressed_tests.iteritems():
      if not regressed_tests:
        continue
      logging.debug(
          'Build %s has %s regressed test names to email.',
          tpl_build, len(regressed_tests))
      preprocessed_html = []
      # Move work to Django templates. Django prefers lists of dicts.
      tpl_regressed_tests = []
      for test_name, regressed_keys in regressed_tests.iteritems():
        test_name_keys = []
        tpl_regressed_tests.append({
            'test_name': test_name,
            'test_path': self.GetTestPath(test_name),
            'test_keys': test_name_keys})
        preprocessed_html.extend(
            self.PreprocessorHTML(test_name, regressed_keys))
        # Organize the keys with their corresponding plots.
        for test_key, regressed_stats in regressed_keys.iteritems():
          if self.IsPreprocessedKey(test_key):
            continue
          test_key_headers = set()
          test_key_stats = []
          stat_keys = regressed_stats.keys()
          stat_keys.sort()
          sort_key = regressed_stats[stat_keys[0]]
          for stat_key in stat_keys:
            stat_data = regressed_stats[stat_key]
            test_key_headers.add(stat_key.replace('_', ' '))
            if type(stat_data) == float:
              stat_data = self._float_converter.Convert(stat_data)
            test_key_stats.append({
                'stat_name': stat_key, 'stat_val': stat_data})

          test_name_keys.append({
              'test_key': test_key,
              'key_plot': self.GetPlotLink(test_name, test_key),
              'key_headers': sorted(test_key_headers),
              'key_stats': test_key_stats,
              'sort_key': sort_key})

      # Inline build log.
      use_json = False
      tpl_build_log = ''

      # Assemble the final email.
      tpl_board = self._board_type
      tpl_netbook = self._netbook
      tpl_preprocessed_html = ''.join(preprocessed_html)
      body = render_to_response(
          os.path.join('emails', PERFORMANCE_REGRESSED_EMAIL), locals()).content

      # Assemble a build performance page.
      tpl_last_updated = self._dash_view.GetFormattedLastUpdated()
      performance_file = '%s_%s' % (tpl_build, BUILD_PERFORMANCE_FILE)
      dash_util.SaveHTML(
          os.path.join(self.GetPerformanceDir(), performance_file),
          render_to_response(
              os.path.join('tables/performance', BUILD_PERFORMANCE_FILE),
              locals()).content)

      # Send it.
      subject = 'Performance keyvals for %s(%s) on %s' % (
          tpl_board, tpl_build, tpl_netbook[8:])
      self.SendEmail(subject, body)


def AlertAll(dash_base_dir, dash_view, dash_options):
  """All the work of checking and sending email.

  Args:
    dash_base_dir: Base dir of the output files.
    dash_view: Reference to our data model.
    dash_options: From alert_config.json.
  """

  plot_options = dash_options['plots']
  for alert in dash_options['alerts']:
    categories = alert['categories']
    use_sheriffs = alert['sheriffs']
    cc = alert['cc']
    test_name = alert['test']
    preprocess_functions = None
    if 'preprocess' in alert:
      preprocess_functions = alert['preprocess']
    perf_checks = alert['checks']

    if not use_sheriffs and not cc:
      logging.warning('Email requires sheriffs or cc.')
      continue

    if not categories or not test_name or not perf_checks:
      logging.warning('Alerts require categories, test and checks.')
      continue

    for platform in alert['platforms']:
      for board, netbook in platform.iteritems():
        notifier = AlertEmailNotifier(
            dash_base_dir, netbook, board, use_sheriffs, cc, plot_options)
        expanded_checks = notifier.ExpandWildcardKeys(test_name, perf_checks)
        if preprocess_functions:
          notifier.PreProcess(
              (categories, test_name, expanded_checks), preprocess_functions)
        notifier.CheckItems((categories, test_name, expanded_checks))
        notifier.GenerateEmail()


if __name__ == '__main__':
  print 'Run %s with --alert-generate.' % DASHBOARD_MAIN
