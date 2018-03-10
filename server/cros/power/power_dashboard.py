# Copyright (c) 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros.power import power_dashboard

class ServerTestDashboard(power_dashboard.BaseDashboard):
    """Dashboard class for autotests that run on server side.
    """

    def __init__(self, logger, testname, host, resultsdir=None, uploadurl=None):
        """Create ServerTestDashboard objects.

        Args:
            logger: object that store the log. This will get convert to
                    dictionary by self._convert()
            testname: name of current test
            resultsdir: directory to save the power json
            uploadurl: url to upload power data
            host: autotest_lib.server.hosts.cros_host.CrosHost object of DUT
        """

        self._host = host
        super(ServerTestDashboard, self).__init__(logger, testname, resultsdir,
                                                  uploadurl)

    def _create_dut_info_dict(self, power_rails):
        """Create a dictionary that contain information of the DUT.

        Args:
            power_rails: list of measured power rails

        Returns:
            DUT info dictionary
        """
        dut_info_dict = {
            'board': self._host.get_board().replace('board:', ''),
            'version': {
                'hw': self._host.get_hardware_revision(),
                'milestone': self._host.get_chromeos_release_milestone(),
                'os': self._host.get_release_version(),
                'channel': self._host.get_channel(),
                'firmware': self._host.get_firmware_version(),
                'ec': self._host.get_ec_version(),
                'kernel': self._host.get_kernel_version(),
            },
            'sku' : {
                'cpu': self._host.get_cpu_name(),
                'memory_size': self._host.get_mem_total_gb(),
                'storage_size': self._host.get_disk_size_gb(),
                'display_resolution': self._host.get_screen_resolution(),
            },
            'ina': {
                'version': 0,
                'ina': power_rails,
            },
            'note': '',
        }

        if self._host.has_battery():
            # Round the battery size to nearest tenth because it is fluctuated
            # for platform without battery nominal voltage data.
            dut_info_dict['sku']['battery_size'] = round(
                    self._host.get_battery_size(), 1)
            dut_info_dict['sku']['battery_shutdown_percent'] = \
                    self._host.get_low_battery_shutdown_percent()
        return dut_info_dict

