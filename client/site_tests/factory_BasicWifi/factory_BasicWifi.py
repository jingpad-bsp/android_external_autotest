# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Basic wifi test -- succeeds if it can see any AP (optionally from a set).


import sys

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from autotest_lib.client.cros import flimflam_test_path
import flimflam


class factory_BasicWifi(test.test):
    version = 1

    def run_once(self, target_ssids=None):
        """Try to find at least one wifi SSID."""

        factory.log('%s run_once' % self.__class__)

        flim = flimflam.FlimFlam()

        found_ssids = set([])
        for service in flim.GetObjectList('Service'):
            properties = service.GetProperties(utf8_strings=True)
            if properties.get('Type', None) != 'wifi':
                continue
            if 'Name' not in properties:
                continue
            found_ssids.add(properties['Name'])
        if not found_ssids:
            raise error.TestFail("No SSIDs found.")
        factory.log('found SSIDs: %s' % ', '.join(found_ssids))
        if target_ssids:
            if not (target_ssids & found_ssids):
                raise error.TestFail("None of the target SSIDs found.")

        factory.log('%s run_once finished' % self.__class__)
