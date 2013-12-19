# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.networking import shill_proxy

class network_DefaultProfileCreation(test.test):
    """The Default Profile Creation class.

    Wipe the default profile, start shill, and check that a default
    profile has been created.

    Test that the default profile contains default values for properties
    that should have them.

    """
    DEFAULT_PROFILE_PATH = '/var/cache/shill/default.profile'
    EXPECTED_SETTINGS = [
        # From DefaultProfile::LoadManagerProperties
        'CheckPortalList=ethernet,wifi,cellular',
        'IgnoredDNSSearchPaths=gateway.2wire.net',
        'LinkMonitorTechnologies=wifi',
        'PortalURL=http://www.gstatic.com/generate_204',
        'PortalCheckInterval=30',
        ]
    version = 1


    def run_once(self):
        """Test main loop."""
        utils.run('stop shill')
        os.remove(self.DEFAULT_PROFILE_PATH)
        utils.run('start shill')
        shill_proxy.ShillProxy.get_proxy()

        profile = open(self.DEFAULT_PROFILE_PATH).read()
        for setting in self.EXPECTED_SETTINGS:
            if setting not in profile:
                logging.error('Did not find setting %s', setting)
                logging.error('Full profile contents are:\n%s', profile)
                raise error.TestFail('Missing setting(s) in default profile.')
