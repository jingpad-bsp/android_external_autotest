# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django report view implementation.

   This class produces a Django HttpResponse object with a series
   of iframes - each with a src link to a chart.

   CLASSES:

   ReportView: base class.

   FUNCTIONS:

   PlotReport(): The principal entry-point.
"""


import os
import simplejson

from django.shortcuts import render_to_response

from autotest_lib.frontend.croschart.charterrors import ChartInputError


FIELD_SEPARATOR = ','


def PlotReport(request, template_file):
  """Base Report plotter with no cache awareness."""

  tpl_params = request.GET
  # Pass through all the parameters except testkeys.
  param_list = []
  for k, value_list in request.GET.lists():
    if not k == 'testkey':
      for v in value_list:
        param_list.append('%s=%s' % (k, v))
  tpl_chart_url = '&'.join(param_list)

  # Split up the test-key tuples
  tpl_charts = []
  test_key_tuples = request.GET.getlist('testkey')
  if test_key_tuples:
    for t in test_key_tuples:
      test_name, test_key = t.split(FIELD_SEPARATOR)
      if not test_key:
        raise ChartInputError('testkey must be a test,key pair.')
      tpl_charts.append((test_name, test_key))
  else:
    tpl_charts = simplejson.load(open(os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'croschart_defaults.json')))
  # Generate a page of iframes.
  return render_to_response(template_file, locals())
