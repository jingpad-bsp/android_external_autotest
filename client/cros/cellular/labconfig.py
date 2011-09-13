# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib
import json

class ConfigError(Exception):
  pass

class LabConfig(object):
  def __init__(self, config):
    self._config = config

  def GetCellByName(self, name):
    for cell in self._config["cells"]:
      if cell["name"] == name:
        return cell
    raise ConfigError("No cell named '%s'" % name)

class JsonLabConfig(LabConfig):
  def __init__(self, json_str):
    super(JsonLabConfig, self).__init__(json.loads(json_str))

class JsonUrlLabConfig(JsonLabConfig):
  def __init__(self, url):
    super(JsonUrlLabConfig, self).__init__(urllib.urlopen(url).read())
