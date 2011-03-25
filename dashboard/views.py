# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import django.http

def handle_summary(request):
    return django.http.HttpResponse("Here you are.")
