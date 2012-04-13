# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrap everything we do with builds in a dash class."""

import commands
import json
import logging
import os
import re
import time
import urllib

import dash_util

# String resources.
from dash_strings import BUILDTIME_PREFIX
from dash_strings import LOCAL_TMP_DIR
from dash_strings import WGET_CMD


class BuildInfo(object):
  """Data and functions from build log."""

  class __impl:
    """Nested class implements code wrapped by singleton."""

    def __init__(self):
      # Store build entries as {started_time, finished_time, chrome_version}
      # indexed by board and build#.
      self._build_time_cache = {}
      self._formatted_time_cache = {}
      self._chrome_version_cache = {}
      self._chrome_parse = re.compile(
          "^Started chromeos-base/chromeos-chrome-([\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3})_rc.*", re.M)

    def GetChromeVersion(self, board, build):
      # Get the string w.x.y.z Chrome version and a zzzz svn revision.
      self.FetchBuildInfo(board, build)
      return self._build_time_cache[board][build]['chrome_version']

    def GetStartedTime(self, board, build):
      # This is a float - seconds since the epoch.
      self.FetchBuildInfo(board, build)
      return self._build_time_cache[board][build]['started_time']

    def GetFinishedTime(self, board, build):
      # This is a float - seconds since the epoch.
      self.FetchBuildInfo(board, build)
      return self._build_time_cache[board][build]['finished_time']

    def GetElapsedTime(self, board, build):
      # This is a float.
      return (
          self.GetFinishedTime(board, build) -
          self.GetStartedTime(board, build))

    def GetFormattedTime(self, time_seconds, short=None):
      if short:
        # Formatted as: Wed 09/08 12:37.
        result = time.strftime('%a %m/%d %H:%M', time.localtime(time_seconds))
      else:
        # Formatted as: Wed Sep 8 12:37:56 2010.
        result = time.ctime(time_seconds)
      return result

    def GetFormattedStartedTime(self, board, build, short=None):
      return self.GetFormattedTime(
          self.GetStartedTime(board, build), short)

    def GetFormattedFinishedTime(self, board, build, short=None):
      return self.GetFormattedTime(
          self.GetFinishedTime(board, build), short)

    def GetFormattedElapsedTime(self, board, build, short=None):
      time_seconds = self.GetElapsedTime(board, build)
      if short:
        # Formatted as: 06:16:12.
        result = time.strftime('%H:%M:%S', time.gmtime(time_seconds))
      else:
        # Formatted as: 04 hrs, 27 mins, 03 secs.
        result = time.strftime(
            '%H hrs, %M mins, %S secs', time.gmtime(time_seconds))
      return result

    def GetFormattedBuildTimes(self, board, build):
      """Perf optimize on the pattern on repeat/retrieval of all."""
      time_key = (board, build)
      if time_key in self._formatted_time_cache:
        return self._formatted_time_cache[time_key]
      result = (self.GetFormattedStartedTime(board, build),
                self.GetFormattedFinishedTime(board, build),
                self.GetFormattedElapsedTime(board, build),
                self.GetFormattedFinishedTime(board, build, True))
      self._formatted_time_cache[time_key] = result
      return result

    def FetchChromeVersion(self, full_build):
      """Grab the Chrome version from the chromeos-images version map."""
      chromeos_build = full_build.split('_')[-1].split('-')[0]
      if chromeos_build in self._chrome_version_cache:
        return self._chrome_version_cache[chromeos_build]
      map_file = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                              'chromeos-chrome-version.json')
      if not os.path.exists(map_file):
        return (None, None)
      chrome_versions = json.load(open(map_file))
      if not chrome_versions or not chromeos_build in chrome_versions:
        return (None, None)
      dot_version = chrome_versions[chromeos_build]
      omaha_url = 'http://omahaproxy.appspot.com/revision?version=%s' % (
          dot_version)
      omaha_wget = '%s "%s"' % (WGET_CMD, omaha_url)
      svn_revision = commands.getoutput(omaha_wget)
      results = (dot_version, svn_revision)
      self._chrome_version_cache[chromeos_build] = results
      return results

    def GetCacheFilename(self, board, build, dir=True):
      filename = '%s%s_%s' % (BUILDTIME_PREFIX, board, build)
      if dir:
        return '%s/%s' % (LOCAL_TMP_DIR, filename)
      else:
        return filename

    def FetchBuildInfo(self, board, build):
      """Load start_time, end_time into memory from file cache or web lookup."""
      # Use an in-memory cache (dictionary) for repeats.
      board_builds = self._build_time_cache.setdefault(board, {})
      build_keys = board_builds.setdefault(build, {})
      if not build_keys:
        build_keys['started_time'] = 0.0
        build_keys['finished_time'] = 0.0
        build_keys['chrome_version'] = [None, None]

        build_log_json = None
        cache_filename = self.GetCacheFilename(board, build)
        if os.path.isfile(cache_filename):
          f = open(cache_filename, 'r')
          build_log_text = f.read()
          if build_log_text:
            build_log_json = json.loads(build_log_text)
          f.close()
        else:
          if not os.path.exists(LOCAL_TMP_DIR):
            os.makedirs(LOCAL_TMP_DIR, 0755)
          dash_util.SaveHTML(cache_filename, '')

    def PruneTmpFiles(self, dash_view):
      """Remove cached build_time data that is no longer useful."""

      build_set = set()
      for board in dash_view.GetBoardTypes():
        for build in dash_view.GetBoardtypeBuilds(board):
          build_set.add(unicode(self.GetCacheFilename(board, build, False)))
      files_set = set(os.listdir(LOCAL_TMP_DIR))
      for f in files_set - build_set:
        if f.find(BUILDTIME_PREFIX) > -1:
          logging.info('Pruning %s from %s.', f, LOCAL_TMP_DIR)
          os.remove('%s/%s' % (LOCAL_TMP_DIR, f))

    def ShowCache(self):
      logging.debug("*")
      logging.debug("*BUILDINFO CACHE***************")
      logging.debug("*")
      for board, build_times in self._build_time_cache.iteritems():
        for build, time_info in build_times.iteritems():
          logging.debug("  %s: %s: %s ~ %s (%s).",
              board, build,
              time_info['started_time'],
              time_info['finished_time'],
              time_info['chrome_version'])

  # Instance reference for singleton behavior.
  __instance = None
  __refs = 0

  def __init__(self):
    if BuildInfo.__instance is None:
      BuildInfo.__instance = BuildInfo.__impl()

    self.__dict__["_BuildInfo__instance"] = BuildInfo.__instance
    BuildInfo.__refs += 1

  def __del__(self):
    BuildInfo.__refs -= 1
    if not BuildInfo.__instance is None and BuildInfo.__refs == 0:
      BuildInfo.__instance.ShowCache()
      del BuildInfo.__instance
      BuildInfo.__instance = None

  def __getattr__(self, attr):
    return getattr(BuildInfo.__instance, attr)

  def __setattr__(self, attr, value):
    return setattr(BuildInfo.__instance, attr, value)
