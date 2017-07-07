# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import common
from autotest_lib.server import test
from autotest_lib.site_utils import acts_lib
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import dnsname_mangler
from autotest_lib.server import afe_utils


class android_EasySetup(test.test):
    """A test that does nothing except setup a phone.

    This test will only setup a phone how a user wants and will perform no
    tests.
    """
    version = 1

    def run_once(self,
                testbed=None,
                install_sl4a=True,
                additional_apks=[]):
        """When run the testbed will be setup.

        @param testbed: The testbed to setup.
        @param install_sl4a: When true sl4a will be installed.
        @param additional_apks: An array of apk info dictionaries.
                                apk = Name of the apk (eg. sl4a.apk)
                                package = Name of the package (eg. test.tools)
                                artifact = Name of the artifact, if not given
                                           package is used.
        """
        hostname = testbed.hostname
        if dnsname_mangler.is_ip_address(hostname):
            testbed_name = hostname
        else:
            testbed_name = hostname.split('.')[0]

        valid_hosts = []
        for v in testbed.get_adb_devices().values():
            try:
                afe_utils.get_host_attribute(v, v.job_repo_url_attribute)
            except error.AutoservError:
                pass
            else:
                valid_hosts.append(v)

        if not valid_hosts:
            logging.error('No valid devices.')
            return

        testbed_env = acts_lib.AndroidTestingEnvironment(
                devices=valid_hosts,
                testbed_name=testbed_name)

        if install_sl4a:
            testbed_env.install_sl4a_apk()

        for apk in additional_apks:
            testbed_env.install_apk(apk)
