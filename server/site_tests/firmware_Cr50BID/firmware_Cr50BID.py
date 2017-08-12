# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import cr50_utils, tpm_utils
from autotest_lib.server import autotest
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50BID(Cr50Test):
    """Verify cr50 board id behavior on a board id locked image.

    Check that cr50 will not accept mismatched board ids when it is running a
    board id locked image.

    Set the board id on a non board id locked image and verify cr50 will
    rollback when it is updated to a mismatched board id image.
    """
    version = 1

    TEST_BOARD_ID = 'TEST'
    TEST_MASK = 0xffff
    TEST_FLAGS = 0xff00

    ORIGINAL = 'original'
    BID_LOCKED = 'board_id_locked'

    # Board id locked debug files will use the board id, mask, and flags in the
    # gs filename
    BID_FILE_INFO = [TEST_BOARD_ID, hex(TEST_MASK), hex(TEST_FLAGS)]
    BID_MISMATCH = ['Board ID mismatched, but can not reboot.']
    BID_ERROR = 5
    SUCCESS = 0

    # The board id locked image is built with the board id of TEST, a mask of
    # 0xffff, and a flag value of 0xff00. The signer only takes in ints you can
    # use these values to create the right image
    #  "board_id": 1413829460,
    #  "board_id_mask": 65535,
    #  "board_id_flags": 65280,
    #
    # BID_TEST_CASES is a list with the the board id and flags to test tests to
    # run. Each item in the list is a list of [board_id, flags, exit status].
    # exit_status should be BID_ERROR if the board id and flags should not be
    # compatible with the board id locked image.
    #
    # A image without board id should be able to run on a device with all of
    # the board id and flag combinations.
    #
    # When using a non-symbolic board id, make sure the length of the string is
    # greater than 4. If the string length is less than 4, usb_updater will
    # treat it as a symbolic string
    # ex: bid of 0 needs to be given as '0x0000'. If it were given as '0', the
    # board id value would be interpreted as ord('0')
    BID_TEST_CASES = [
        [TEST_BOARD_ID, 0, BID_ERROR],
        [TEST_BOARD_ID, TEST_FLAGS, SUCCESS],
        [TEST_BOARD_ID, TEST_FLAGS | 1, SUCCESS],
        [TEST_BOARD_ID, TEST_FLAGS ^ (1 << 10), BID_ERROR],
        [TEST_BOARD_ID, cr50_utils.ERASED_BID_INT, SUCCESS],

        ['ST', TEST_FLAGS, SUCCESS],
        ['TeST', TEST_FLAGS, SUCCESS],
        ['TEsT', TEST_FLAGS, BID_ERROR],
        ['0x54455354', TEST_FLAGS, SUCCESS],
        ['0x00005354', TEST_FLAGS, SUCCESS],
        ['0x54450000', TEST_FLAGS, BID_ERROR],
        ['0x000', 0, BID_ERROR],
        ['0xffffffff', 0xffff, BID_ERROR],
    ]

    # Settings to test all of the cr50 BID responses. The dictionary conatins
    # the name of the BID verification as the key and a list as a value.
    #
    # The value of the list is the image to start running the test with then
    # the method to update to the board id locked image as the value.
    #
    # If the start image is 'board_id_locked', we won't try to update to the
    # board id locked image.
    BID_TEST_TYPE = {
        # Verify that the board id locked image rejects invalid board ids
        'get/set' : BID_LOCKED,

        # Verify the cr50 response when doing a normal update to a board id
        # locked image. If there is a board id mismatch, cr50 should rollback
        # to the image that was already running.
        'rollback' : ORIGINAL,

        # TODO (mruthven): add support for verifying recovery
        # Certain devices are not able to successfully jump to the recovery
        # image when the TPM is locked down. We need to find a way to verify the
        # DUT is in recovery without being able to ssh into the DUT.
    }

    def initialize(self, host, cmdline_args, dev_path='', bid_path=''):

        # Restore the original image, rlz code, and board id during cleanup.
        super(firmware_Cr50BID, self).initialize(host, cmdline_args,
                                                 restore_cr50_state=True,
                                                 cr50_dev_path=dev_path)
        if self.cr50.using_ccd():
            raise error.TestNAError('Use a flex cable instead of CCD cable.')

        if not self.cr50.has_command('bid'):
            raise error.TestNAError('Cr50 image does not support board id')

        self.dev_path = self.get_saved_cr50_dev_path()
        self.original_path = self.get_saved_cr50_original_path()
        self.save_board_id_locked_image(bid_path)

        self.client_at = autotest.Autotest(self.host)
        # Clear the RLZ so ChromeOS doesn't set the board id during the updates.
        cr50_utils.SetRLZ(self.host, '')


    def save_board_id_locked_image(self, bid_path):
        """Get the board id locked image"""
        if os.path.isfile(bid_path):
            self.board_id_locked_path = bid_path
        else:
            devid = self.servo.get('cr50_devid')
            # TODO(mruthven): once they are released switch to using prod signed
            # board id locked images
            self.board_id_locked_path = self.download_cr50_debug_image(
                devid, self.BID_FILE_INFO)


    def cleanup(self):
        """Clear the TPM Owner"""
        super(firmware_Cr50BID, self).cleanup()
        tpm_utils.ClearTPMOwnerRequest(self.host)


    def reset_state(self, image_type):
        """Update to the image and erase the board id.

        We can't erase the board id unless we are running a debug image. Update
        to the debug image so we can erase the board id and then rollback to the
        right image.

        Args:
            image_type: the name of the image we want to be running at the end
                        of reset_state: 'original' or 'board_id_locked'. This
                        image name needs to correspond with some test attribute
                        ${image_type}_path

        Raises:
            TestFail if the board id was not erased
        """
        self.cr50_update(self.dev_path)

        # Rolling back will take care of erasing the board id
        self.cr50_update(getattr(self, image_type + '_path'), rollback=True)

        # Verify the board id was erased
        if cr50_utils.GetBoardId(self.host) != cr50_utils.ERASED_BID:
            raise error.TestFail('Could not erase bid')


    def updater_set_bid(self, bid, flags, exit_code):
        """Set the flags using usb_updater and verify the result

        Args:
            board_id: board id string
            flags: An int with the flag value
            exit_code: the expected error code. 0 if it should succeed

        Raises:
            TestFail if usb_updater had an unexpected exit status or setting the
            board id failed
        """

        original_bid, _, original_flags = cr50_utils.GetBoardId(self.host)

        if exit_code:
            exit_code = 'Error %d while setting board id' % exit_code

        try:
            cr50_utils.SetBoardId(self.host, bid, flags)
            result = self.SUCCESS
        except error.AutoservRunError, e:
            result = e.result_obj.stderr.strip()

        if result != exit_code:
            raise error.TestFail("Unexpected result setting %s:%x expected "
                                 "'%s' got '%s'" %
                                 (bid, flags, exit_code, result))

        # Verify cr50 is still running with the same board id and flags
        if exit_code:
            cr50_utils.CheckBoardId(self.host, original_bid, original_flags)


    def run_bid_test(self, image_name, bid, flags, bid_error):
        """Set the bid and flags. Verify a board id locked image response

        Update to the right image type and try to set the board id. Only the
        board id locked image should reject the given board id and flags.

        If we are setting the board id on a non-board id locked image, try to
        update to the board id locked image afterwards to verify that cr50 does
        or doesn't rollback. If there is a bid error, cr50 should fail to update
        to the board id locked image.


        Args:
            image_name: The image name 'original', 'dev', or
                        'board_id_locked'
            bid: A string representing the board id. Either the hex or symbolic
                 value
            flags: A int value for the flags to set
            bid_error: The expected usb_update error code. 0 for success 5 for
                       failure
        """
        is_bid_locked_image = image_name == self.BID_LOCKED

        # If the image is not board id locked, it should accept any board id and
        # flags
        exit_code = bid_error if is_bid_locked_image else self.SUCCESS

        response = 'error %d' % exit_code if exit_code else 'success'
        logging.info('EXPECT %s setting bid to %s:%x with %s image',
                     response, bid, flags, image_name)

        # Reset the board id and update to the correct image
        self.reset_state(image_name)

        # Try to set the board id and flags
        self.updater_set_bid(bid, flags, exit_code)

        # If it failed before, it should fail with the same error. If we already
        # set the board id, it should fail because the board id is already set.
        self.updater_set_bid(bid, flags, exit_code if exit_code else 7)

        # After setting the board id with a non boardid locked image, try to
        # update to the board id locked image. Verify that cr50 does/doesn't run
        # it. If there is a mismatch, the update should fail and Cr50 should
        # rollback to the original image.
        if not is_bid_locked_image:
            self.cr50_update(self.board_id_locked_path,
                             expect_rollback=(not not bid_error))


    def run_once(self):
        """Verify the Cr50 BID response of each test bid."""
        for test_type, image_name in self.BID_TEST_TYPE.iteritems():
            logging.info('VERIFY: BID %s', test_type)
            for bid, flags, bid_error in self.BID_TEST_CASES:
                self.run_bid_test(image_name, bid, flags, bid_error)
