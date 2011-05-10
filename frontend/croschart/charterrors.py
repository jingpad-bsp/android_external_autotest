# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class ChartError(Exception):
  """Local exception to be raised by code in this file."""
  pass


class ChartInputError(ChartError):
  """Problem with the URL formatting."""
  def __init__(self, msg):
    self.msg = msg


class ChartDBError(ChartError):
  """Problem retrieving the data."""
  def __init__(self, msg):
    self.msg = msg
