# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


""" The autotest performing FW update, both EC and AP."""


import logging
import os
import time

from autotest_lib.client.common_lib import autotemp
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import test, utils
from autotest_lib.server.cros import provision
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers


_CONFIG = global_config.global_config
# pylint: disable-msg=E1120
_IMAGE_URL_PATTERN = _CONFIG.get_config_value(
        'CROS', 'firmware_url_pattern', type=str)
_AFE = frontend_wrappers.RetryingAFE(
        timeout_min=1, delay_sec=10, debug=False)


class provision_FirmwareUpdate(test.test):
    """A test that can provision a machine to the correct firmware version."""


    version = 1
    UNTAR_TIMEOUT = 60
    DOWNLOAD_TIMEOUT = 60


    def initialize(self, host, value):
        """Initialize the test.

        @param host:  a CrosHost object of the machine to update.
        @param value: the provisioning value, which is the build version
                      to which we want to provision the machine,
                      e.g. 'link-firmware/R22-2695.1.144'.
        """
        self._hostname = host.hostname
        # TODO(fdeng): use host.get_board() after
        # crbug.com/271834 is fixed.
        self._board = host._get_board_from_afe()
        self._build = value
        self._ap_image = 'image-%s.bin' % self._board
        self._ec_image = 'ec.bin'
        self.tmpd = autotemp.tempdir(unique_id='fwimage')
        self._servo = host.servo
        if not self._servo:
            raise error.TestError('Host %s does not have servo.' %
                                  host.hostname)
        try:
            ds = dev_server.ImageServer.resolve(self._build)
            ds.stage_artifacts(self._build, ['firmware'])
        except dev_server.DevServerException as e:
            raise error.TestFail(str(e))
        fwurl = _IMAGE_URL_PATTERN % (ds.url(), self._build)
        local_tarball = os.path.join(self.tmpd.name,
                                     os.path.basename(fwurl))
        utils.system('wget -O %s %s' % (local_tarball, fwurl),
                     timeout=self.DOWNLOAD_TIMEOUT)
        utils.system('tar xf %s -C %s %s %s' % (
                local_tarball, self.tmpd.name,
                self._ap_image, self._ec_image), timeout=self.UNTAR_TIMEOUT)
        utils.system('tar xf %s  --wildcards -C %s "dts/*"' % (
                local_tarball, self.tmpd.name), timeout=self.UNTAR_TIMEOUT,
                ignore_status=True)


    def cleanup(self):
        """Extend cleanup to clean temporary dir."""
        super(provision_FirmwareUpdate, self).cleanup()
        self.tmpd.clean()


    def _clear_version_labels(self):
        """Clear firmware version labels from the machine."""
        labels = _AFE.get_labels(name__startswith=provision.FW_VERSION_PREFIX,
                                host__hostname=self._hostname)
        for label in labels:
            label.remove_hosts(hosts=[self._hostname])


    def _add_version_label(self):
        """Add firmware version label to the machine."""
        fw_label = ':'.join([provision.FW_VERSION_PREFIX, self._build])
        provision.ensure_label_exists(fw_label)
        label = _AFE.get_labels(name__startswith=fw_label)[0]
        label.add_hosts([self._hostname])


    def run_once(self):
        """The method called by the control file to start the test."""
        self._clear_version_labels()
        logging.info('Will re-program EC now')
        self._servo.program_ec(self._board,
                               os.path.join(self.tmpd.name, self._ec_image))
        logging.info('Will re-program bootprom now')
        self._servo.program_bootprom(
                self._board,
                os.path.join(self.tmpd.name, self._ap_image))
        self._servo.get_power_state_controller().cold_reset()
        time.sleep(self._servo.BOOT_DELAY)
        self._add_version_label()
