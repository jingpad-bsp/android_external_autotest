# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import cr50_utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest
from autotest_lib.server.cros import gsutil_wrapper


class Cr50Test(FirmwareTest):
    """
    Base class that sets up helper objects/functions for cr50 tests.
    """
    version = 1

    CR50_GS_URL = 'gs://chromeos-localmirror-private/distfiles/chromeos-cr50-%s/'
    CR50_DEBUG_FILE = 'cr50_dbg_%s.bin'
    CR50_PROD_FILE = 'cr50.%s.bin.prod'

    def initialize(self, host, cmdline_args, restore_cr50_state=False,
                   cr50_dev_path=''):
        super(Cr50Test, self).initialize(host, cmdline_args)

        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')

        self._original_cr50_rw_version = self.cr50.get_version()
        self.host = host
        self._original_state_saved = False

        if restore_cr50_state:
            self._save_node_locked_dev_image(cr50_dev_path)
            self._save_original_state()
            self._original_state_saved = True


    def _save_node_locked_dev_image(self, cr50_dev_path):
        """Save or download the node locked dev image.

        Args:
            cr50_dev_path: The path to the node locked cr50 image.

        Raise:
            TestError if we cannot find a node locked dev image for the device.
        """
        if os.path.isfile(cr50_dev_path):
            self._node_locked_cr50_image = cr50_dev_path
        else:
            devid = self.servo.get('cr50_devid')
            try:
                self._node_locked_cr50_image = self.download_cr50_debug_image(
                    devid)
            except Exception, e:
                raise error.TestError('Cannot restore the device state without '
                                      'a node-locked DBG image')


    def _save_original_state(self):
        """Save the cr50 related state.

        Save the device's current cr50 version, cr50 board id, rlz, and image
        at /opt/google/cr50/firmware/cr50.bin.prod. These will be used to
        restore the state during cleanup.
        """
        # Save the RO and RW Versions, the device RLZ code, and the cr50 board
        # id.
        self._original_cr50_version = cr50_utils.GetRunningVersion(self.host)
        self._original_rlz = cr50_utils.GetRLZ(self.host)
        self._original_cr50_bid = cr50_utils.GetBoardId(self.host)

        # Save the image currently stored on the device
        binver = cr50_utils.GetBinVersion(self.host)
        filename = 'device_image_' + self._original_cr50_version[1]
        self._original_device_image = os.path.join(self.resultsdir, filename)
        self.host.get_file(cr50_utils.CR50_FILE, self._original_device_image)

        # If the running cr50 version matches the image on the DUT use that
        # as the original image. If the versions don't match download the image
        # from google storage
        if self._original_cr50_version[1] == binver[1]:
            self._original_cr50_image = self._original_device_image
        else:
            self._original_cr50_image = self.download_cr50_release_image(
                self._original_cr50_version[1])
        logging.info('cr50 version: %r', self._original_cr50_version)
        logging.info('rlz: %r', self._original_rlz)
        logging.info('cr50 bid: %08x:%08x:%08x', self._original_cr50_bid[0],
            self._original_cr50_bid[1], self._original_cr50_bid[2])
        logging.info('DUT cr50 image version: %r', binver)


    def get_saved_cr50_original_path(self):
        """Return the local path for the original cr50 image"""
        if not hasattr(self, '_original_device_image'):
            raise error.TestError('No record of original image')
        return self._original_device_image


    def get_saved_cr50_dev_path(self):
        """Return the local path for the cr50 dev image"""
        if not hasattr(self, '_node_locked_cr50_image'):
            raise error.TestError('No record of debug image')
        return self._node_locked_cr50_image


    def _restore_original_image(self):
        """Restore the cr50 image and erase the state.

        Make 3 attempts to update to the original image. Use a rollback from
        the DBG image to erase the state that can only be erased by a DBG image.
        """
        # Remove the image at /opt/google/cr50/firmware/cr50.bin.prod, so
        # cr50-update wont update cr50 while we are rolling back.
        self.host.run('rm /opt/google/cr50/firmware/cr50.bin.prod')
        self.host.run('sync')

        for i in range(3):
            try:
                # Update to the node-locked DBG image so we can erase all of
                # the state we are trying to reset
                self.cr50_update(self._node_locked_cr50_image)

                # Rollback to the original cr50 image.
                self.cr50_update(self._original_cr50_image, rollback=True)
                break
            except Exception, e:
                logging.warning('Failed to restore original image attempt %d: '
                                '%r', i, e)


    def _restore_original_state(self):
        """Update to the original image"""
        # Delete the RLZ code before updating to make sure that chromeos doesn't
        # set the board id during the update.
        cr50_utils.SetRLZ(self.host, '')

        # Update to the original image and erase the board id
        self._restore_original_image()

        # The board id can only be set once. Set it before reinitializing the
        # RLZ code to make sure that ChromeOS won't set the board id.
        if self._original_cr50_bid != cr50_utils.ERASED_BID:
            # Convert the board_id to at least a 5 char string, so usb_updater
            # wont treat it as a symbolic value.
            cr50_utils.SetBoardId(self.host,
                                  '0x%03x' % self._original_cr50_bid[0],
                                  self._original_cr50_bid[2])
        # Set the RLZ code
        cr50_utils.SetRLZ(self.host, self._original_rlz)
        # Copy the original /opt/google/cr50/firmware image back onto the DUT.
        cr50_utils.InstallImage(self.host, self._original_device_image)
        # Make sure the /var/cache/cr50* state is restored
        cr50_utils.ClearUpdateStateAndReboot(self.host)

        mismatch = []
        erased_rlz = not self._original_rlz
        # The vpd rlz code and mosys platform brand should be in sync, but
        # check both just in case.
        brand = self.host.run('mosys platform brand', ignore_status=erased_rlz)
        if ((not brand != erased_rlz) or
            (brand and brand.stdout.strip() != self._original_rlz)):
            mismatch.append('mosys platform brand')
        if cr50_utils.GetRLZ(self.host) != self._original_rlz:
            mismatch.append('vpd rlz code')
        if cr50_utils.GetBoardId(self.host) != self._original_cr50_bid:
            mismatch.append('cr50 board_id')
        if (cr50_utils.GetRunningVersion(self.host) !=
            self._original_cr50_version):
            mismatch.append('cr50_version')
        if len(mismatch):
            raise error.TestError('Failed to restore original device state: %s'
                                  % ', '.join(mismatch))
        logging.info('Successfully restored the original cr50 state')


    def cleanup(self):
        """Make sure cr50 is running the same image"""
        if self._original_state_saved:
            self._restore_original_state()

        running_ver = self.cr50.get_version()
        if (hasattr(self, '_original_cr50_rw_version') and
            running_ver != self._original_cr50_rw_version):
            raise error.TestError('Running %s not the original cr50 version '
                                  '%s' % (running_ver,
                                  self._original_cr50_rw_version))

        super(Cr50Test, self).cleanup()


    def find_cr50_gs_image(self, filename, image_type=None):
        """Find the cr50 gs image name

        Args:
            filename: the cr50 filename to match to
            image_type: release or debug. If it is not specified we will search
                        both the release and debug directories
        Returns:
            a tuple of the gsutil bucket, filename
        """
        gs_url = self.CR50_GS_URL % (image_type if image_type else '*')
        gs_filename = os.path.join(gs_url, filename)
        bucket, gs_filename = utils.gs_ls(gs_filename)[0].rsplit('/', 1)
        return bucket, gs_filename


    def download_cr50_gs_image(self, filename, bucket=None, image_type=None):
        """Get the image from gs and save it in the autotest dir

        Returns:
            the local path
        """
        if not bucket:
            bucket, filename = self.find_cr50_gs_image(filename, image_type)

        remote_temp_dir = '/tmp/'
        src = os.path.join(remote_temp_dir, filename)
        dest = os.path.join(self.resultsdir, filename)

        # Copy the image to the dut
        gsutil_wrapper.copy_private_bucket(host=self.host,
                                           bucket=bucket,
                                           filename=filename,
                                           destination=remote_temp_dir)

        self.host.get_file(src, dest)
        return dest


    def download_cr50_debug_image(self, devid, board_id_info=None):
        """download the cr50 debug file

        Get the file with the matching devid and board id info

        Args:
            devid: the cr50_devid string '${DEVID0} ${DEVID1}'
            board_id_info: a list of [board id, board id mask, board id
                                      flags]
        Returns:
            the local path to the debug image
        """
        filename = self.CR50_DEBUG_FILE % (devid.replace(' ', '_'))
        if board_id_info:
            filename += '.' + '.'.join(board_id_info)
        return self.download_cr50_gs_image(filename, image_type='debug')


    def download_cr50_release_image(self, rw_ver, board_id_info=None):
        """download the cr50 release file

        Get the file with the matching version and board id info

        Args:
            rw_ver: the rw version string
            board_id_info: a list of strings [board id, board id mask, board id
                          flags]
        Returns:
            the local path to the release image
        """
        filename = self.CR50_PROD_FILE % rw_ver
        if board_id_info:
            filename += '.' + '.'.join(board_id_info)
        return self.download_cr50_gs_image(filename, image_type='release')


    def _cr50_verify_update(self, expected_ver, expect_rollback):
        """Verify the expected version is running on cr50

        Args:
            expect_ver: The RW version string we expect to be running
            expect_rollback: True if cr50 should have rolled back during the
                             update

        Raises:
            TestFail if there is any unexpected update state
        """
        running_ver = self.cr50.get_version()
        if expected_ver != running_ver:
            raise error.TestFail('Unexpected update ver running %s not %s' %
                                 (running_ver, expected_ver))

        if expect_rollback != self.cr50.rolledback():
            raise error.TestFail('Unexpected rollback behavior: %srollback '
                                 'detected' % 'no ' if expect_rollback else '')

        logging.info('RUNNING %s after %s', expected_ver,
                     'rollback' if expect_rollback else 'update')


    def _cr50_run_update(self, path):
        """Install the image at path onto cr50

        Args:
            path: the location of the image to update to

        Returns:
            the rw version of the image
        """
        tmp_dest = '/tmp/' + os.path.basename(path)

        dest, image_ver = cr50_utils.InstallImage(self.host, path, tmp_dest)
        cr50_utils.UsbUpdater(self.host, ['-s', dest])
        return image_ver[1]


    def cr50_update(self, path, rollback=False, erase_nvmem=False,
                    expect_rollback=False):
        """Attempt to update to the given image.

        If rollback is True, we assume that cr50 is already running an image
        that can rollback.

        Args:
            path: the location of the update image
            rollback: True if we need to force cr50 to rollback to update to
                      the given image
            erase_nvmem: True if we need to erase nvmem during rollback
            expect_rollback: True if cr50 should rollback on its own

        Raises:
            TestFail if the update failed
        """
        original_ver = self.cr50.get_version()

        rw_ver = self._cr50_run_update(path)

        # Running the update may cause cr50 to reboot. Wait for that before
        # sending more commands. The reboot should happen quickly. Wait a
        # maximum of 10 seconds.
        self.cr50.wait_for_reboot(10)

        if erase_nvmem and rollback:
            self.cr50.erase_nvmem()

        # Don't erase flashinfo during rollback. That would mess with the board
        # id
        if rollback:
            self.cr50.rollback()

        expected_ver = original_ver if expect_rollback else rw_ver
        # If we expect a rollback, the version should remain unchanged
        self._cr50_verify_update(expected_ver, rollback or expect_rollback)
