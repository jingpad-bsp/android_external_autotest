# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from django.conf.urls import defaults
import common

urlpatterns = defaults.patterns(
    '',
    (r'^(?P<boards>[\w\-&]*)/'
      '(?P<netbook>[\w\-]*)/'
      '(?P<from_build>0\.\d{1,3}\.\d{1,3}\.\d{1,3})/'
      '(?P<to_build>0\.\d{1,3}\.\d{1,3}\.\d{1,3})/'
      '(?P<test_name>[\w\-\.]+)/'
      '(?P<test_key>[\w\-\.]+)/'
      '(?P<width>[\d]+)/'
      '(?P<height>[\d]+)/$',
      'frontend.croschart.views.PlotChartFromBuilds'),
    (r'^(?P<boards>[\w\-&]+)/'
      '(?P<netbook>[\w\-]+)/'
      '(?P<test_name>[\w\-\.]+)/'
      '(?P<test_key>[\w\-\.]+)/'
      '(?P<width>[\d]+)/'
      '(?P<height>[\d]+)/$',
      'frontend.croschart.views.PlotChartInterval'),
    (r'^charts/'
      '(?P<boards>[\w\-&]+)/'
      '(?P<netbook>[\w\-]+)/'
      '(?P<from_build>0\.\d{1,3}\.\d{1,3}\.\d{1,3})/'
      '(?P<to_build>0\.\d{1,3}\.\d{1,3}\.\d{1,3})/'
      '(?P<test_key_names>[\w\-,&\.]+)/'
      '(?P<width>[\d]+)/'
      '(?P<height>[\d]+)/$',
      'frontend.croschart.views.FrameChartsTestsKeys'),
    (r'^charts/'
      '(?P<boards>[\w\-&]+)/'
      '(?P<netbook>[\w\-]+)/'
      '(?P<width>[\d]+)/'
      '(?P<height>[\d]+)/$',
      'frontend.croschart.views.FrameChartsBoardNetbook'))
