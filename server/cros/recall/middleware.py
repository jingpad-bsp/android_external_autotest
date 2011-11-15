# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Middleware classes for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["DeterministicScriptInjector"]

import logging
import re

from http_client import HTTPClient, HTTPMiddleware


class DeterministicScriptInjector(HTTPMiddleware):
  """Mutate HTTP Requests to inject Deterministic JavaScript code.

  Implements HTTP Client middleware that alters text/html responses,
  inserting a <script> block to the top of the page that replaces the
  JavaScript Math.random() and Date() functions for deterministic
  behaviour.

  The Date() replacement uses the original request time as the returned
  value, to avoid issues where scripts loop while the date remains the
  same, the date is incremented between calls. However since scripts may
  be executed out of order, the date is only incremented every
  date_count_threshold calls.
  """
  logger = logging.getLogger("DeterministicScriptInjector")

  _html_re = re.compile(r'<html[^>]*>', re.IGNORECASE)
  _head_re = re.compile(r'<head[^>]*>', re.IGNORECASE)
  _body_re = re.compile(r'<body[^>]*>', re.IGNORECASE)

  _deterministic_script = """\
<script>
  (function () {
    var orig_date = Date;
    var random_count = 0;
    var date_count = 0;
    var random_seed = 0.462;
    var time_seed = @@START_TIME@@;
    var random_count_threshold = 25;
    var date_count_threshold = 25;
    Math.random = function() {
      random_count++;
      if (random_count > random_count_threshold){
        random_seed += 0.1;
        random_count = 1;
      }
      return (random_seed % 1);
    };
    Date = function() {
      if (this instanceof Date) {
        date_count++;
        if (date_count > date_count_threshold){
          time_seed += 50;
          date_count = 1;
        }
        switch (arguments.length) {
        case 0: return new orig_date(time_seed);
        case 1: return new orig_date(arguments[0]);
        default: return new orig_date(arguments[0], arguments[1],
           arguments.length >= 3 ? arguments[2] : 1,
           arguments.length >= 4 ? arguments[3] : 0,
           arguments.length >= 5 ? arguments[4] : 0,
           arguments.length >= 6 ? arguments[5] : 0,
           arguments.length >= 7 ? arguments[6] : 0);
        }
      }
      return new Date().toString();
    };
    Date.__proto__ = orig_date;
    Date.prototype.constructor = Date;
    orig_date.now = function() {
      return new Date().getTime();
    };
  })();
</script>
"""

  def __call__(self, request):
    """Lookup the request.

    Args:
        request: HTTPRequest to lookup.

    Returns:
        HTTPResponse reply, which may include an error response.
    """
    response = self.http_client(request)

    content_type = response.getheader('Content-Type')
    if content_type and content_type.startswith('text/html'):
      self.logger.debug("Will inject script into %r for %s", response, request)

      start_time = int(response.start_time * 1000)
      self._inject_script = self._deterministic_script.replace(
          '@@START_TIME@@', str(start_time))
      response.AddMutateFunction(self._MutateChunk)

    return response

  def _InjectScriptAfter(self, match):
    return match.group(0) + self._inject_script

  def _MutateChunk(self, chunk):
    if self._inject_script:
      count = 0
      if chunk:
        chunk, count = self._head_re.subn(self._InjectScriptAfter, chunk, 1)
        if count:
          self.logger.debug("Injected script into HEAD")
          self._inject_script = None
        else:
          chunk, count = self._body_re.subn(self._InjectScriptAfter, chunk, 1)
          if count:
            self.logger.debug("Injected script into BODY")
            self._inject_script = None

    return chunk
