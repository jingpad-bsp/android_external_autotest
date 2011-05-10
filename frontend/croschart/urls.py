# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from django.conf.urls import defaults
import common


COMMON_URL = r'[\w\-.=&]+'

# Order is important. chartdiff and chartreport must come before chart.
urlpatterns = defaults.patterns(
    'frontend.croschart.views',
    (r'^chartdiff?%s$' % COMMON_URL, 'PlotChartDiff'),
    (r'^chartreport?%s$' % COMMON_URL, 'PlotChartReport'),
    (r'^chart?%s$' % COMMON_URL, 'PlotChart'))
