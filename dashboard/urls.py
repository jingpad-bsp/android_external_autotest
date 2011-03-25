# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
   
from django.conf.urls import defaults
import common

urlpatterns = defaults.patterns(
        '',
        (r'^dashboard/summary/', 'dashboard.views.handle_summary'))
