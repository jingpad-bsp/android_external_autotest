# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for django urls code to invoke views."""

import datetime

from django.http import HttpResponse
from django.shortcuts import render_to_response

import autotest_lib.frontend.croschart.validators as validators
import autotest_lib.frontend.croschart.chartmodels as chartmodels
import autotest_lib.frontend.croschart.chartviews as chartviews
import autotest_lib.frontend.croschart.reportviews as reportviews

from autotest_lib.frontend.croschart.charterrors import ChartInputError


VLISTS = {
    'chart': {
        'from_build': [validators.CrosChartValidator,
                       validators.BuildRangeValidator],
        'from_date': [validators.CrosChartValidator,
                      validators.DateRangeValidator],
        'interval': [validators.CrosChartValidator,
                     validators.IntervalRangeValidator]},
    'chartreport': {
        'from_build': [validators.CrosReportValidator,
                       validators.BuildRangeValidator],
        'from_date': [validators.CrosReportValidator,
                      validators.DateRangeValidator],
        'interval': [validators.CrosReportValidator,
                     validators.IntervalRangeValidator]},
    'releasereport': {
        'from_build': [validators.CrosReportValidator,
                       validators.BuildRangeValidator]},
    'testreport': {
        'from_date': [validators.DateRangeValidator],
        'interval': [validators.IntervalRangeValidator]}}


def ValidateParameters(request, vlist):
  """Returns a list of appropriate validators."""
  # Catches when no interval supplied.
  for range_key in vlist.keys() + [None]:
    if request.GET.get(range_key, None):
      break
  if not range_key:
    raise ChartInputError('One interval-type parameter must be supplied.')
  validators.Validate(request, vlist[range_key])
  if range_key == 'interval':
    salt = datetime.date.isoformat(datetime.date.today())
  else:
    salt = None
  return salt


def PlotChart(request):
  """Plot the requested chart from /chart?..."""
  try:
    salt = ValidateParameters(request, VLISTS['chart'])
    return chartviews.PlotChart(
        request, 'plot_chart.html',
        chartmodels.GetRangedKeyByBuildLinechartData, salt)
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())


def PlotChartDiff(request):
  """Plot the requested chart from /chartdiff?... and a split diff view."""
  try:
    salt = ValidateParameters(request, VLISTS['chart'])
    return chartviews.PlotChart(
        request, 'plot_chartdiff.html',
        chartmodels.GetRangedKeyByBuildLinechartData, salt)
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())


def PlotChartReport(request):
  """Plot the requested report from /report?..."""
  try:
    ValidateParameters(request, VLISTS['chartreport'])
    return reportviews.PlotReport(request, 'plot_chartreport.html')
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())


def PlotReleaseReport(request):
  """Plot the requested report from /releasereport?..."""
  try:
    salt = ValidateParameters(request, VLISTS['releasereport'])
    return chartviews.PlotChart(
        request, 'plot_releasereport.html',
        chartmodels.GetReleaseReportData, salt)
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())


def PlotTestReport(request):
  """Plot the requested report from /testreport?..."""
  try:
    salt = ValidateParameters(request, VLISTS['testreport'])
    return chartviews.PlotChart(
        request, 'plot_testreport.html',
        chartmodels.GetRangedTestReportData, salt)
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())


def PlotLabTestReport(request):
  """Plot the requested report from /labtestreport?..."""
  try:
    salt = ValidateParameters(request, VLISTS['testreport'])
    return chartviews.PlotChart(
        request, 'plot_labtestreport.html',
        chartmodels.GetRangedLabTestReportData, salt)
  except ChartInputError as e:
    tpl_hostname = request.get_host()
    return render_to_response('plot_syntax.html', locals())
