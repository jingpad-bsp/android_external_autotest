# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utility functions shared by multiple dashboard modules.

   Alphabetical where no dependency on another function.

   Functions: BuildNumberCmp
              MakeChmodDirs
              PruneOldDirsFiles
              SaveHTML
              ShowList
              ShowDict
              ShowStructure
              UrlFix

   Classes: DebugFunctionTiming
            DebugTiming
            HumanReadableFloat
            SimpleCounter
"""

import datetime
import decimal
import inspect
import logging
import os
import re
import shutil
import urllib
import urlparse

from time import time

BUILD_PARSE = re.compile('((?:[\d]+\.)?[\d]+\.[\d]+\.[\d]+)')


def SplitBuild(build):
  """Find and split pure version number.

  From R18-xx.yy.zz => ['xx', 'yy', 'zz]
  From R18-xx.yy.zz-a1-b2 => ['xx', 'yy', 'zz]
  From 0.xx.yy.zz-a1-b2 => ['xx', 'yy', 'zz]

  Ignores old '-a1-bXXX' fields.
  """
  m = re.search(BUILD_PARSE, build)
  if m:
    return m.group(1).split('.')
  else:
    logging.debug('Unexpected build: %s.', build)
  return build


def BuildNumberCmp(build1, build2):
  """Compare build numbers and return in descending order."""
  major1 = SplitBuild(build1)
  major2 = SplitBuild(build2)

  major_len = min([len(major1), len(major2)])
  for i in xrange(major_len):
    if major1[i] != major2[i]:
      return -cmp(int(major1[i]), int(major2[i]))
  return -cmp(build1, build2)


def PruneOldDirsFiles(path, dirs=True, older_than_days=60):
  """Helper to prune dirs that are older.

  Job cache directory can easily exceed 32k limit.
  Prune older jobs.

  The waterfall/test displays of crash data do not
  generally exceed 3 weeks of results so choosing
  60 days is reasonable with a buffer.

  Args:
    path: parent container directory to scan/prune.
    dirs: True to prune dirs, False to prune files.
    older_than: prune dirs older than this many days.
  """
  target_timedelta = datetime.timedelta(days=older_than_days)
  now_seconds = time()
  for entry in os.listdir(path):
    entry = os.path.join(path, entry)
    alive_seconds = now_seconds - os.path.getmtime(entry)
    if datetime.timedelta(seconds=alive_seconds) > target_timedelta:
      if dirs and os.path.isdir(entry):
        shutil.rmtree(entry)
      if not dirs and os.path.isfile(entry):
        os.remove(entry)

def MakeChmodDirs(path):
  """Helper to make and chmod dirs."""

  return_code = os.system('mkdir -p %s' % path)
  if return_code:
    logging.error('mkdir (%s) exit status %s', path, return_code)
  return_code = os.system('chmod -R 0755 %s' % path)
  if return_code:
    logging.error('chmod (%s) exit status %s', path, return_code)


def SaveHTML(html_file, html_content, style_section=None):
  """Helper to write our HTML files."""
  f = open(html_file, 'w')
  if style_section:
    f.write(style_section)
  f.write(html_content)
  f.close()
  os.chmod(html_file, 0644)


def ShowList(current_list, indent=2):
  str_list = [str(s) for s in current_list]
  logging.debug("%s%s.", " " * indent, ", ".join(str_list))


def ShowDict(current_dict, indent=2):
  for k, v in current_dict.iteritems():
    if type(v) == list:
      logging.debug("%s%s.", " " * indent, k)
      ShowList(v, indent+2)
    elif type(v) == set:
      logging.debug("%s%s.", " " * indent, k)
      ShowList(list(v), indent+2)
    elif type(v) == dict:
      logging.debug("%s%s.", " " * indent, k)
      ShowDict(v, indent+2)
    else:
      logging.debug("%s%s: %s.", " " * indent, k, unicode(v))


def ShowStructure(title, var, doc=None):
  logging.debug("*")
  logging.debug("*%s***************", title)
  logging.debug("*")
  if doc:
    logging.debug(doc)
    logging.debug("*")
  if not var:
    logging.debug("None")
  elif type(var) == list:
    ShowList(var)
  elif type(var) == set:
    ShowList(list(var))
  elif type(var) == dict:
    ShowDict(var)
  else:
    logging.debug(str(var))


def UrlFix(url):
    """Escapes a URL according to RFC2616."""
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(url)
    path = urllib.quote(path, '/%')
    qs = urllib.quote_plus(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


class DebugFunctionTiming(object):
  def __init__(self):
    # Use the name of the parent frame record.
    self._function_name = 'function: ' + inspect.stack()[2][3]
    self._start_time = datetime.datetime.now()

  def GetElapsed(self):
    return self._function_name, (datetime.datetime.now() - self._start_time)


class DebugTiming(object):
  """Class for simple timing of arbitrary blocks of code.

  USE:
    diag = dash_util.DebugTiming()
    ...block of code
    del diag
  """

  class __impl:
    """Nested class implements code wrapped by singleton."""

    def __init__(self):
      self._functions = {}

    def ShowFunctionTiming(self):
      logging.debug("*")
      logging.debug("*DEBUG FUNCTION TIMING***************")
      logging.debug("*")
      functions = self._functions.keys()
      functions.sort()
      for name in functions:
        logging.debug("  %s: %s.",
            name, str(self._functions[name]))

    def __del__(self):
      self.ShowFunctionTiming()

    def UpdateFunctionTime(self, name, elapsed):
      name_time = self._functions.setdefault(name, datetime.timedelta(0))
      self._functions[name] = name_time + elapsed


  # Instance reference for singleton behavior.
  __instance = None
  __refs = 0
  __functiontiming = []

  def __init__(self):
    if DebugTiming.__instance is None:
      DebugTiming.__instance = DebugTiming.__impl()

    self.__dict__["_DebugTiming__instance"] = DebugTiming.__instance
    DebugTiming.__refs += 1

    DebugTiming.__functiontiming.insert(0, DebugFunctionTiming())

  def __del__(self):
    timing = DebugTiming.__functiontiming.pop(0)
    name, elapsed = timing.GetElapsed()
    DebugTiming.__instance.UpdateFunctionTime(name, elapsed)
    del timing

    DebugTiming.__refs -= 1
    if not DebugTiming.__instance is None and DebugTiming.__refs == 0:
      del DebugTiming.__instance
      DebugTiming.__instance = None

  def __getattr__(self, attr):
    return getattr(DebugTiming.__instance, attr)

  def __setattr__(self, attr, value):
    return setattr(DebugTiming.__instance, attr, value)


class HumanReadableFloat(object):
  """Class for converting floats to be human readable."""

  def __init__(self, use_short=True, use_suffix=None):
    if use_suffix:  # Byte, Second...
      self._suffix = use_suffix
    else:
      self._suffix = ''
    self._prefixes = ' ,kilo,Mega,Giga,Tera,Peta,Exa,Zetta,Yotta'.split(',')
    if use_short:
      self._prefixes = [pre[0] for pre in self._prefixes]
      if self._suffix:
        self._suffix = self._suffix[0]

  def Convert(self, number, precision=3):
    if not type(number) == 'string':
      number = str(number)
    decimal_location = number.find('.')
    suffix_index = (decimal_location - 1) / 3
    if decimal_location > 3:
      # Put the decimal in the right spot
      new_decimal_location = decimal_location - suffix_index * 3
      number = list(number)
      number.remove('.')
      number.insert(new_decimal_location, '.')
    return '%s%s%s' % (
        round(float(''.join(number)), precision),
        self._prefixes[suffix_index],
        self._suffix)

  def BackToFloat(self, number_string):
    return float(number_string[:-1])


class SimpleCounter(object):
  """Simple: a flavor of the Python Counter."""
  def __init__(self):
    """Track the 'counter' and the largest entry only."""
    self._counter = {}
    self._max_key = None
    self._max_val = -1

  def Push(self, k):
    """Enter new value and update largest tracking."""
    if k:
      self._counter[k] = self._counter.get(k, 0) + 1
      if self._counter[k] > self._max_val:
        self._max_key = k
        self._max_val = self._counter[k]

  def MaxKey(self):
    """Retrieve the largest."""
    if self._max_key and len(self._counter) > 1:
      return '%s (multiple)' % self._max_key
    else:
      return self._max_key
