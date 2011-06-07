# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django chart view implementation.

   This class produces a Django HttpResponse object with a chart.

   CLASSES:

   ChartView: base class.

   FUNCTIONS:

   PlotChart(): The principal entry-point.
"""

import base64
import hashlib
import os

from django.http import HttpResponse
from django.shortcuts import render_to_response

from autotest_lib.frontend.croschart.charterrors import ChartDBError
from autotest_lib.frontend.croschart.charterrors import ChartInputError


UPDATECACHE = 'updatecache'  # url parameter for cache debugging


def PlotChart(request, template_file, chart_data_fn, salt=None):

  def GetRequestHash(request, salt=None, ignored_parameters=[]):
    """Retrieve a hash value of the whole url with query parameters.

    Use of the same query parameters in different order should produce the
    same hash.  This extends to multiple values passed for one key.  The
    differing order should not affect the hash. This code builds a psuedo
    url string.  Trailing separators (,&) are not removed for efficiency.

    Args:
      request: Django HttpRequest object
      salt: string to optionally contribute to the hash if needed.
      ignored_parameters: List of parameter keys that should not be considered
                          in the hash fn. This strips debugging parameters.
    """
    if not request:
      return None
    norm_url = [request.path]
    if salt:
      norm_url.append('/')
      norm_url.append(salt)
    norm_url.append('?')
    for k in sorted(request.GET.keys()):
      # Ignore cache control parameter in building cache filename.
      # This allows the cache to be refreshed.
      if k in ignored_parameters:
        continue
      norm_url.append(k)
      norm_url.append('=[')
      for v in sorted(request.GET.getlist(k)):
        norm_url.append(v)
        norm_url.append(',')
      norm_url.append(']&')
    return base64.urlsafe_b64encode(hashlib.sha256(''.join(norm_url)).digest())

  def ReadCachedChart(cache_path):
    """Read chart html from the cached file if present."""
    rendered_response = None
    if os.path.exists(cache_path):
      f = open(cache_path, 'r')
      rendered_response = HttpResponse(f.read())
      f.close()
    return rendered_response

  def WriteChartToCache(cache_path, rendered_response):
    """Write a chart to the cache."""
    f = open(cache_path, 'w')
    f.write(rendered_response.content)
    f.close()

  def GenerateChart(request, template_file, chart_data_fn):
    """Read chart data from the DB and generate new chart html."""
    try:
      # Need to remove updatecache from the url string so that
      # future invocations without it match this retrieval.
      if UPDATECACHE in request.GET:
        qd = request.GET.copy()
        del qd[UPDATECACHE]
        tpl_path = '%s?%s' % (request.path, qd.urlencode())
      else:
        tpl_path = request.get_full_path()
      tpl_diffpath = tpl_path.replace('chart?', 'chartdiff?')
      tpl_params = request.GET
      tpl_chart = chart_data_fn(request)
      tpl_colors = ['red', 'blue', 'green', 'black']
      return render_to_response(template_file, locals())
    except ChartDBError as e:
      return render_to_response('plot_unavailable.html', locals())

  """Base Chart plotter with cache awareness."""
  full_cache_path = os.path.join(
      os.path.abspath(os.path.dirname(__file__)), '.cache',
      GetRequestHash(request=request, salt=salt,
                     ignored_parameters=[UPDATECACHE]))
  rendered_response = None
  update_cache = request.GET.get(UPDATECACHE, None)
  if not update_cache or not update_cache.lower() == 'true':
    rendered_response = ReadCachedChart(full_cache_path)
  if not rendered_response:
    # Generate a response from the db.
    rendered_response = GenerateChart(request, template_file, chart_data_fn)
    WriteChartToCache(full_cache_path, rendered_response)
  return rendered_response
