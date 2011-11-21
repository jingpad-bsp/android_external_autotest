# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions called to preprocess perf data for regressions."""

import logging
import operator

import dash_util

# String resources.
from dash_strings import PREPROCESSED_TAG
from dash_strings import EMAIL_ALERT_DELTA_TABLE_SKELETON
from dash_strings import EMAIL_ALERT_DELTA_TABLE_ROW

PREFIX_LEN = 9

class PreprocessFunctions(object):
  """Class to contain and invoke preprocessing functions."""

  def Invoke(self, function_name, params, keyvals, checks):
    """Dispatch function and return True if failed."""
    if not hasattr(self, function_name):
      logging.debug('Preprocessing function %s not found.', function_name)
      return False
    return getattr(self, function_name)(params, keyvals, checks)

  def _MakePreprocessedKey(self, key, seq=None):
    """Helper to distinguish created preprocessing keys from regulars."""
    new_key = '%s%s' % (key, PREPROCESSED_TAG)
    if seq:
      new_key = '%s%s%s' % (seq, PREPROCESSED_TAG, new_key)
    return new_key

  def _IsPreprocessedKey(self, key):
    """Helper to decide if a key was produced by us."""
    key_len = len(key)
    pp_len = len(PREPROCESSED_TAG)
    return key[key_len-pp_len:] == PREPROCESSED_TAG, pp_len, key_len

  def _GetOriginalKeySeq(self, key):
    """Helper to distinguish created preprocessing keys from regulars."""
    new_key = ''
    seq = 0
    is_pp, pp_len, key_len = self._IsPreprocessedKey(key)
    if is_pp:
      new_key = key[:key_len-pp_len]
    n = new_key.find(PREPROCESSED_TAG)
    if n > -1:
      seq = int(new_key[:n])
      new_key = new_key[n+pp_len:]
    return new_key, seq

  def IsPreprocessedKey(self, key):
    is_pp, _, _ = self._IsPreprocessedKey(key)
    return is_pp

  def PreprocessorHTML(self, test_name, regressed_keys):
    """Process preprocessed keys and related details into a summary."""
    # Preserve order using seq hints.
    preprocessed_in_order = []
    preprocessed_details = {}
    for test_key, regressed_stats in regressed_keys.iteritems():
      build_val = regressed_stats['build_mean']
      build_npoints = regressed_stats['build_samples']
      expected_val = regressed_stats['historical_mean']
      expected_npoints = regressed_stats['historical_samples']
      is_pp, _, _ = self._IsPreprocessedKey(test_key)
      if is_pp:
        orig_key, seq = self._GetOriginalKeySeq(test_key)
        details_row = preprocessed_details.setdefault(
            orig_key, [0.0, 0.0, 0.0, 0.0])
        details_row[0] = build_val
        details_row[1] = expected_val
        preprocessed_in_order.append((orig_key, seq))
      else:
        details_row = preprocessed_details.setdefault(
            test_key, [0.0, 0.0, 0.0, 0.0])
        details_row[2] = build_val
        details_row[3] = expected_val
    preprocessed_in_order.sort(key=operator.itemgetter(1))

    # Build html.
    converter = dash_util.HumanReadableFloat()
    current_table = []
    table_list = [current_table]
    previous_key = None
    for one_key, seq in preprocessed_in_order:
      if previous_key and (previous_key[:PREFIX_LEN] != one_key[:PREFIX_LEN]):
        current_table = []
        table_list.append(current_table)
      pp_build_val, pp_expected_val, build_val, expected_val = (
          preprocessed_details[one_key])
      current_table.append(
          EMAIL_ALERT_DELTA_TABLE_ROW % {
              'key': one_key,
              'pp_latest': converter.Convert(pp_build_val),
              'pp_average': converter.Convert(pp_expected_val),
              'latest': converter.Convert(build_val),
              'average': converter.Convert(expected_val)})
      previous_key = one_key

    preprocessed_html = []
    for current_table in table_list:
      preprocessed_html.append(
          EMAIL_ALERT_DELTA_TABLE_SKELETON % {
              'test_name': test_name,
              'body': ''.join(current_table)})
    return preprocessed_html

  def GroupDeltas(self, params, keyvals, checks):
    """Create new keyvals using deltas based on existing keyvals."""
    # Average the values for each checked key and build into a structure
    # just like the existing keyvals.
    stub_test_id = 0
    key_build_averages = {}
    build_key_counts = {}
    for one_key in checks:
      key_build_averages[one_key] = {}
      for build, values in keyvals[one_key].iteritems():
        key_set = build_key_counts.setdefault(build, set())
        key_set.add(one_key)
        key_build_averages[one_key][build] = (
            [sum(values[0], 0.0) / len(values[0])], [stub_test_id])

    # Figure out the relative order of the keys in increasing
    # order of one build's average values. Use the build with the
    # most keys as a reference.
    high_water_build = None
    high_water_count = 0
    for build, key_set in build_key_counts.iteritems():
      if len(key_set) > high_water_count:
        high_water_count = len(key_set)
        high_water_build = build
    averages = []
    for one_key in checks:
      if (not high_water_build or
          not high_water_build in key_build_averages[one_key]):
        logging.warning(
            'Key %s is missing build %s in GroupDeltas().',
            one_key, high_water_build)
      else:
        averages.append((
            one_key, key_build_averages[one_key][high_water_build][0]))
    averages.sort(key=operator.itemgetter(1))

    # Generate the new keys that use deltas as values.
    # Group them according to a prefix on each key.
    prefix_groups = {}
    for one_key, _ in averages:
      key_list = prefix_groups.setdefault(one_key[:PREFIX_LEN], [])
      key_list.append(one_key)

    i = 1  # For later sorting of the group by value.
    delta_prefix_groups = prefix_groups.keys()
    delta_prefix_groups.sort()
    for one_key_group in delta_prefix_groups:
      previous_key = None
      for one_key in prefix_groups[one_key_group]:
        new_key_name = self._MakePreprocessedKey(one_key, i)
        # Add the new key to the checks.
        checks[new_key_name] = checks[one_key]

        # Add the new key and data into keyvals.
        if previous_key:
          # Calculate the deltas of calculated averages.
          for build in key_build_averages[one_key].iterkeys():
            if (build in key_build_averages[one_key] and
                build in key_build_averages[previous_key]):
              new_keyval = keyvals.setdefault(new_key_name, {})
              new_keyval[build] = ([
                  key_build_averages[one_key][build][0][0] -
                  key_build_averages[previous_key][build][0][0]],
                  [stub_test_id])
        else:
          # Copy the structure from the averages calculated.
          keyvals[new_key_name] = key_build_averages[one_key]
        previous_key = one_key
        i += 1
