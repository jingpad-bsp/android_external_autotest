# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utility functions.

   Used by >1 module.
"""


import json
import logging
import os
import re


FIELD_SEPARATOR = ','
BUILD_PART_SEPARATOR = ' '

BUILD_PATTERN1 = re.compile(
    '([\w\-]+-r[c0-9]+)-([\d.]+)-([ar][\w]*)-(b[\d]+)')
BUILD_PATTERN2 = re.compile(
    '([\w\-]+-r[\w]+)-(R[\d]+-[\d]+\.[\d]+\.[\d]+)-([ar][\w]*)-(b[\d]+)')


def AbbreviateBuild(build, chrome_versions, with_board=False):
  """Condense full build string for x-axis representation."""
  m = re.match(BUILD_PATTERN1, build)
  if not m or not len(m.groups()) == 4:
    m = re.match(BUILD_PATTERN2, build)
  if not m or not len(m.groups()) == 4:
    logging.warning('Skipping poorly formatted build: %s.', build)
    return None
  chrome_version = ''
  release_part, build_part, sequence_part = m.group(1, 2, 4)
  if build_part[0] == 'R':
    chrome_lookup = build_part.split('-')[1]
  else:
    chrome_lookup = build_part
  if chrome_versions and chrome_lookup in chrome_versions:
    chrome_version = '%s(%s)' % (BUILD_PART_SEPARATOR,
                                 chrome_versions[chrome_lookup])
  if with_board:
    new_build = '%s%s%s-%s%s' % (release_part, BUILD_PART_SEPARATOR,
                                 build_part, sequence_part, chrome_version)
  else:
    new_build = '%s-%s%s' % (build_part, sequence_part, chrome_version)

  return new_build


def AbridgeCommonKeyPrefix(test_name, test_keys):
  """Easier to read if common part stripped off keys in legend."""
  new_test_keys = test_keys
  if len(test_keys) > 1:
    common_prefix = os.path.commonprefix(test_keys)
    prefix_len = len(common_prefix)
    if prefix_len > 0:
      new_test_keys = []
      test_name += ' - %s' % common_prefix
      for test_key in test_keys:
        new_test_keys.append(test_key[prefix_len:])
  return test_name, new_test_keys


def GetChromeVersions(request):
  """Get Chrome-ChromeOS version map if requested."""
  chrome_versions = None
  chrome_version_flag = request.GET.get('chromeversion', 'true')
  if chrome_version_flag and chrome_version_flag.lower() == 'true':
    map_file = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            'chromeos-chrome-version.json')
    if os.path.exists(map_file):
      chrome_versions = json.load(open(map_file))
  return chrome_versions


def GetTestNameKeys(testkey):
  """Helper to retrieve test_name and test_keys from request."""
  test_name_keys = testkey.split(FIELD_SEPARATOR)
  return test_name_keys[0], test_name_keys[1:]
