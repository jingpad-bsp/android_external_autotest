# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

import django.http
from django.shortcuts import render_to_response
import gviz_api
import simplejson

from autotest_lib.frontend.croschart import models


class ChartException(Exception):
    pass


def CommonPlotChart(boards, netbook, from_build, to_build,
                    test_name, test_key, width, height, interval=None):
  try:
    tpl_gviz_id = '%s-%s' % (test_name, test_key)
    tpl_gviz_title = test_name
    tpl_perf_key = test_key
    tpl_width = width
    tpl_height = height
    gviz_data, tpl_job_tags = models.GetChartData(boards, netbook,
                                                  from_build, to_build,
                                                  test_name, test_key, interval)
    if not gviz_data:
      raise ChartException
    # Use gviz_api to create efficient data tables.
    data_table = gviz_api.DataTable({
        'build': ('string', 'Build'),
        tpl_perf_key: ('number', tpl_perf_key)})
    data_table.LoadData(gviz_data)
    tpl_gviz_js = data_table.ToJSon(['build', tpl_perf_key])
    tpl_colors = ['red', 'blue', 'green', 'black']
    return render_to_response('plot_chart.html', locals())
  except:
    return render_to_response('plot_unavailable.html', locals())


# Responds to restful request.
def PlotChartFromBuilds(request, boards, netbook, from_build, to_build,
                        test_name, test_key, width, height):
  return CommonPlotChart(boards, netbook, from_build, to_build,
                         test_name, test_key, width, height)


def PlotChartInterval(
    request, boards, netbook, test_name, test_key, width, height):
  from_build = to_build = None
  interval = '2 WEEK'
  return CommonPlotChart(boards, netbook, from_build, to_build,
                         test_name, test_key, width, height, interval)


def CommonFrameCharts(tpl_boards, tpl_netbook, tpl_width, tpl_height):
  tpl_charts = simplejson.load(open(
      os.path.join(
          os.path.abspath(os.path.dirname(__file__)),
          'croschart_defaults.json')))
  return render_to_response('charts.html', locals())


def FrameChartsBoardNetbook(request, boards, netbook, width, height):
  return CommonFrameCharts(boards, netbook, width, height)


def FrameChartsTestsKeys(request, boards, netbook, from_build, to_build,
                         test_key_names, width, height):
  tpl_width = width
  tpl_height = height
  tpl_boards = boards
  tpl_netbook = netbook
  tpl_from_build = from_build
  tpl_to_build = to_build
  tpl_charts = [c.split(',') for c in test_key_names.split('&')]
  return render_to_response('charts.html', locals())
