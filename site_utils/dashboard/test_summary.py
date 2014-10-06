# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Retrieve and process the test summary results.json files.

Specifically, this code enables access to information about crashes
identified during job runs.
"""

__author__ = ['truty@google.com (Mike Truty)',
              'dalecurtis@google.com (Dale Curtis)']

import commands
import json
import os

import dash_util

# String resources.
from dash_strings import AUTOTEST_ARCHIVE
from dash_strings import AUTOTEST_PATH
from dash_strings import AUTOTEST_SERVER
from dash_strings import CGI_RETRIEVE_LOGS_CMD
from dash_strings import GSUTIL_GET_CMD
from dash_strings import WGET_CMD

LOG_BASE_PATH = '%s/%s/results.json'


class TestSummaryInfo(object):
  """Class to enable retrieval of test summary info files."""

  def __init__(self, job_cache_dir):
    """Initialize some job status caches.

    There are two caches for job result artifacts: an in-memory one and one
    on disk.
    _job_cache_dir: contains the file-based on-disk cache of job results files.
    _job_summary_cache: an in-memory dictionary of job results for test lookups.

    Args:
      job_cache_dir: base location for the file-based job result cache.
    """
    self._job_cache_dir = job_cache_dir
    self._job_summary_cache = {}

  @staticmethod
  def _GetJsonFromFileOrString(file_or_string, is_file=True):
    """Helper to convert text retrieved to Json.

    Args:
      file_or_string: filename or string to consume.
      is_file: flag to inform logic if open is needed.

    Returns:
      Json version of the string (file text).
    """
    try:
      if is_file:
        with open(file_or_string) as f:
          summary_json = json.load(f)
      else:
        summary_json = json.loads(file_or_string)
    except ValueError:
      # This ValueError raised when json.load(s) finds improper Json text.
      summary_json = {}
    return summary_json

  def _LocalResultFile(self, job_name, base_dir=None, use_json=True):
    """Helper to find and retrieve the results file on a local machine.

    The file may be located in a result dir or a cache dir.

    Args:
      job_name: a key to finding the job data under autotest results.
      base_dir: used to find the job result file cache. If None, look in
                the dashboard job file cache.
      use_json: flag to suggest if Json-parsing is needed.

    Returns:
      If the file is located:
        and use_json=True, then return Json valid version of the file.
        and not use_json=True, then return raw file contents.
      If file not found, return None.
    """
    base_dir = base_dir or self._job_cache_dir
    log_file_path = os.path.abspath(LOG_BASE_PATH % (base_dir, job_name))
    if os.path.isfile(log_file_path):
      if use_json:
        return self._GetJsonFromFileOrString(log_file_path)
      with open(log_file_path) as f:
        return f.read()
    return None

  def _RetrieveResultsJson(self, job_name):
    """Helper to retrieve the results.json file from a result server.

    The tko/retrieve_logs.cgi script handles finding the results server
    and/or retrieving results from gs using gsutil.

    Args:
      job_name: used to locate the job-specific result.json.
    """
    results_base = os.path.join(AUTOTEST_SERVER, CGI_RETRIEVE_LOGS_CMD)
    log_file_path = LOG_BASE_PATH % (results_base, job_name)
    return commands.getoutput('%s %s' % (WGET_CMD, log_file_path))

  def _UpdateFileCache(self, job_name):
    """Helper to update a job file cache with a results Json file.

    This is complicated by the fact that results files may be located
    on the local machine, a local autotest server or remotely on a
    results server or in Google Storage.

    Args:
      job_name: a key to finding the job data under autotest results.

    Returns:
      Json valid version of the file content or None.
    """
    summary_text = self._RetrieveResultsJson(job_name)
    cache_path = os.path.abspath(LOG_BASE_PATH % (self._job_cache_dir,
                                                  job_name))
    dash_util.MakeChmodDirs(os.path.dirname(cache_path))
    dash_util.SaveHTML(cache_path, summary_text)
    return self._GetJsonFromFileOrString(summary_text, is_file=False)

  def RetrieveTestSummary(self, job_tag, test_name):
    """Retrieves test artifacts from the Autotest server for a given test.

    Autotest drops a Json file which contains failed tests, crashes, and log
    file snippets in each job results directory. We use this information to
    reduce wget usage and find crashes for a given job.

    Requests are cached to reduce round-trip time to the server which can be
    very substantial.

    Extract path to results from tag. Sometimes the test['tag'] is:

        <job_name>/<group name>/<host name(s)>

    Other times it's just:

        <job_name>/<host name>

    It depends on how tests were scheduled. Usually, if present, group name
    indicates that the job was spread across multiple hosts.

    The results.json is always in sub directory under <job_name>.

    Args:
      job_tag: Path under Autotest results to find test result file.
      test_name: Used to find previously cached test results.

    Returns:
      Json test artifact if it can be loaded from the Autotest server, None
      otherwise.
    """
    job_name = '/'.join(job_tag.split('/')[0:2])

    # Get job summary from in-memory cache, then the actual file or file cache.
    if job_name not in self._job_summary_cache:
      # Now ensure the file cache is updated since job entry not in memory.
      summary_json = self._LocalResultFile(job_name)
      if summary_json is None:
        summary_json = self._UpdateFileCache(job_name)
      self._job_summary_cache[job_name] = summary_json

    # Return the results for this test if we have them in the cache.
    return self._job_summary_cache[job_name].get(test_name)
