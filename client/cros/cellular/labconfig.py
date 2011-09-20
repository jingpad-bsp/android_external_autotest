# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json, urllib


class LabConfigError(Exception):
  pass

class LabConfig(object):
  def __init__(self, config):
    self._config = config

  def GetCellByName(self, name):
    for cell in self._config["cells"]:
      if cell["name"] == name:
        return cell
    raise LabConfigError("No cell named '%s'" % name)

def make_json_config(json_str):
  config = json.loads(json_str)
  return LabConfig(config)

def fetch_json_config(url):
  json_str = urllib.urlopen(url).read()
  return make_json_config(json_str)

class CellTestArgumentError(Exception):
  pass

def _parse_test_args(raw_args):
  if raw_args[0] != '0':
    raise CellTestArgumentError('Unknown test-args version %s' % raw_args[0])
  if len(raw_args) != 3:
    raise CellTestArgumentError('Wrong number of test-args for version 0')
  return { 'url': raw_args[1], 'cell': raw_args[2] }

def get_test_config(raw_args):
  args = _parse_test_args(raw_args)
  config = fetch_json_config(args['url'])
  return config.GetCellByName(args['cell'])
