# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT config setting overrides for Nyan."""


class Values(object):
    software_sync_update = 6
    chrome_ec = True
    ec_capability = (['battery', 'keyboard', 'arm', 'lid'])
