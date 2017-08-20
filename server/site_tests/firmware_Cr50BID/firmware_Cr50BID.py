# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import cr50_utils, tpm_utils
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50BID(Cr50Test):
    """Verify cr50 board id behavior on a board id locked image.

    Check that cr50 will not accept mismatched board ids when it is running a
    board id locked image.

    Set the board id on a non board id locked image and verify cr50 will
    rollback when it is updated to a mismatched board id image.

    The board id locked test image will be found using the given bid_path or
    downloaded from google storage using the information in bid, bid_mask, and
    bid_flags.

    Release images can be tested by passing in the release version and board
    id. The images on google storage have this in the filename. Use those same
    values for the test.

    If no board id or release version is given, the test will download the
    prebuilt debug image from google storage. It has the board id
    TEST:0xffff:0xff00. If you need to add another device to the lab or want to
    test locally, you can add these values to the manifest to sign the image.
     "board_id": 0x54455354,
     "board_id_mask": 0xffff,
     "board_id_flags": 0xff00,

    You can also use the following command to create the image.
     CR50_BOARD_ID='TEST:ffff:ff00' util/signer/bs

    If you want to use something other than the test board id info, you have to
    input the  bid. bid_mask and bid_flags are optional. They will be set to
    0xffffffff and 0xff00 if they aren't given.

    @param dev_path: path to the node locked dev image.
    @param bid_path: local path for the board id locked image. The other bid
                     args will be ignored, and the board id info will be gotten
                     from the file.
    @param release_ver: The rw version string. Needed if you want to test a
                        released board id locked image. You will also need to
                        give the board id for that file.
    @param bid: string with the symbolic board id. If this isn't given,
                bid_mask and bid_flags will be ignored.
    @param bid_mask: hex string of the bid mask. If bid is given, but this isn't
                     the test will use 0xffffffff.
    @param bid_flags: hex string of the bid flags. If bid is given, but this
                      isn't the test will use 0xff00.
    """
    version = 1

    MAX_BID = 0xffffffff
    DEFAULT_FLAGS = 0xff00
    DEFAULT_MASK = MAX_BID
    TEST_BOARD_ID = 'TEST'
    TEST_MASK = 0xffff
    TEST_FLAGS = DEFAULT_FLAGS

    ORIGINAL = 'original'
    BID_LOCKED = 'board_id_locked'

    # Board id locked debug files will use the board id, mask, and flags in the
    # gs filename
    TEST_BID_FILE_INFO = [TEST_BOARD_ID, TEST_MASK, TEST_FLAGS]
    BID_MISMATCH = ['Board ID mismatched, but can not reboot.']
    BID_ERROR = 5
    SUCCESS = 0

    # BID_BASE_TESTS is a list with the the board id and flags to test for each
    # run. Each item in the list is a list of [board_id, flags, exit status].
    # exit_status should be BID_ERROR if the board id and flags should not be
    # compatible with the board id locked image.
    #
    # A image without board id will be able to run on a device with all of the
    # board id and flag combinations.
    #
    # When using a non-symbolic board id, make sure the length of the string is
    # greater than 4. If the string length is less than 4, usb_updater will
    # treat it as a symbolic string
    # ex: bid of 0 needs to be given as '0x0000'. If it were given as '0', the
    # board id value would be interpreted as ord('0')
    #
    # These base tests are be true no matter the board id, mask, or flags. If a
    # value is None, then it will be replaced with the test board id or flags
    # while running the test.
    BID_BASE_TESTS = [
        [None, None, SUCCESS],

        # All 1s in the board id flags should be acceptable no matter the
        # actual image flags
        [None, MAX_BID, SUCCESS],

        # All 0s or All 1s will fail
        ['0x000', None, BID_ERROR],
        [hex(MAX_BID), None, BID_ERROR],
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

    def initialize(self, host, cmdline_args, dev_path='', bid_path='',
                   release_ver=None, bid=None, bid_mask=None, bid_flags=None):
        # Restore the original image, rlz code, and board id during cleanup.
        super(firmware_Cr50BID, self).initialize(host, cmdline_args,
                                                 restore_cr50_state=True,
                                                 cr50_dev_path=dev_path)
        if self.cr50.using_ccd():
            raise error.TestNAError('Use a flex cable instead of CCD cable.')

        if not self.cr50.has_command('bid'):
            raise error.TestNAError('Cr50 image does not support board id')

        if bid:
            # Replace each bid value with the default value it wasn't provided.
            bid_mask = int(bid_mask, 16) if bid_mask else self.DEFAULT_MASK
            bid_flags = int(bid_flags, 16) if bid_flags else self.DEFAULT_FLAGS
            bid_info = [bid, bid_mask, bid_flags]
        else:
            # Use the TEST bid info if we aren't given a board id
            bid_info = self.TEST_BID_FILE_INFO

        # Save the necessary images.
        self.dev_path = self.get_saved_cr50_dev_path()
        self.original_path = self.get_saved_cr50_original_path()
        self.save_board_id_locked_image(bid_path, release_ver, bid_info)

        # Clear the RLZ so ChromeOS doesn't set the board id during the updates.
        cr50_utils.SetRLZ(self.host, '')

        # Add tests to the test list based on the running board id infomation
        self.build_tests()


    def add_test(self, board_id, flags, expected_result):
        """Add a test case to the list of tests

        The test will see if the board id locked image behaves as expected with
        the given board_id and flags.

        Args:
            board_id: A symbolic string or hex str representing the board id.
            flags: a int value for the flags
            expected_result: SUCCESS if the board id and flags should be
                accepted by the board id locked image. BID_ERROR if it should be
                rejected.
        """
        self.tests.append([board_id, flags, expected_result])


    def add_board_id_tests(self):
        """Create a list of tests based on the board id and mask.

        For each bit set to 1 in the board id image mask, Cr50 checks that the
        bit in the board id infomask matches the image board id. Create a
        couple of test cases based on the test mask and board id to verify this
        behavior.
        """
        bid_int = cr50_utils.GetSymbolicBoardId(self.test_bid)
        mask_str = bin(self.test_mask).split('b')[1]
        mask_str = '0' + mask_str if len(mask_str) < 32 else mask_str
        mask_str = mask_str[::-1]
        zero_index = mask_str.find('0')
        one_index = mask_str.find('1')

        # The hex version of the symbolic string should be accepted.
        self.add_test(hex(bid_int), self.test_flags, self.SUCCESS)

        # Flip a bit we don't care about to make sure it is accepted
        if zero_index != -1:
            test_bid = bid_int ^ (1 << zero_index)
            logging.info('Test Case: image bid %x with test bid %x should '
                         'pass', bid_int, test_bid)
            self.add_test(hex(test_bid), self.test_flags, self.SUCCESS)

        # Flip a bit we care about to make sure it is rejected
        if one_index != -1:
            test_bid = bid_int ^ (1 << one_index)
            logging.info('Test Case: image bid %x with test bid %x should '
                         'fail', bid_int, test_bid)
            self.add_test(hex(test_bid), self.test_flags, self.BID_ERROR)


    def add_flag_tests(self):
        """Create a list of tests based on the test flags.

        When comparing the flag field, cr50 makes sure all 1s set in the image
        flags are also set as 1 in the infomask. Create a couple of test cases
        to verify cr50 responds appropriately to different flags.
        """
        flag_str = bin(self.test_flags).split('b')[1]
        flag_str = '0' + flag_str if len(flag_str) < 32 else flag_str
        zero_index = flag_str.find('0')
        one_index = flag_str.find('1')

        # If we care about any flag bits, setting the flags to 0 should cause
        # a rejection
        if self.test_flags:
            self.add_test(self.test_bid, 0, self.BID_ERROR)

        # Flip a 0 to 1 to make sure it is accepted.
        if zero_index != -1:
            zero_index = flag_str.rindex('0')
            test_flags = self.test_flags | (1 << zero_index)
            logging.info('Test Case: image flags %x with test flags %x should '
                         'pass', self.test_flags, test_flags)
            self.add_test(self.test_bid, test_flags, self.SUCCESS)

        # Flip a 1 to 0 to make sure it is rejected.
        if one_index != -1:
            one_index = flag_str.rindex('1')
            test_flags = self.test_flags ^ (1 << one_index)
            logging.info('Test Case: image flags %x with test flags %x should '
                         'fail', self.test_flags, test_flags)
            self.add_test(self.test_bid, test_flags, self.BID_ERROR)


    def build_tests(self):
        """Add more test cases based on the image board id, flags, and mask"""
        self.tests = self.BID_BASE_TESTS
        self.add_flag_tests()
        self.add_board_id_tests()
        logging.info('Running tests %r', self.tests)


    def save_board_id_locked_image(self, bid_path, release_ver, bid_info):
        """Get the board id locked image"""

        if os.path.isfile(bid_path):
            # If the bid_path exists, use that.
            self.board_id_locked_path = bid_path
            # Install the image on the device to get the image version
            dest = os.path.join('/tmp', os.path.basename(bid_path))
            ver = cr50_utils.InstallImage(self.host, bid_path, dest)[1]
        elif release_ver:
            # Download a release image with the rw_version and board id
            logging.info('Using %s %s release image for test', release_ver,
                         bid_info[0])
            self.board_id_locked_path, ver = self.download_cr50_release_image(
                release_ver, bid_info)
        else:
            logging.info('Using %s DBG image for test', bid_info[0])
            devid = self.servo.get('cr50_devid')
            self.board_id_locked_path, ver = self.download_cr50_debug_image(
                devid, bid_info)

        # Save the image board id
        bid_info = ver[2].split(':')
        self.test_bid = bid_info[0]
        self.test_mask = int(bid_info[1], 16)
        self.test_flags = int(bid_info[2], 16)
        logging.info('Testing with board id locked image %s', bid_info)


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
        if cr50_utils.GetChipBoardId(self.host) != cr50_utils.ERASED_CHIP_BID:
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

        original_bid, _, original_flags = cr50_utils.GetChipBoardId(self.host)

        if exit_code:
            exit_code = 'Error %d while setting board id' % exit_code

        try:
            cr50_utils.SetChipBoardId(self.host, bid, flags)
            result = self.SUCCESS
        except error.AutoservRunError, e:
            result = e.result_obj.stderr.strip()

        if result != exit_code:
            raise error.TestFail("Unexpected result setting %s:%x expected "
                                 "'%s' got '%s'" %
                                 (bid, flags, exit_code, result))

        # Verify cr50 is still running with the same board id and flags
        if exit_code:
            cr50_utils.CheckChipBoardId(self.host, original_bid, original_flags)


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
            for bid, flags, bid_error in self.tests:
                # Replace place holder values with the test values
                bid = bid if bid != None else self.test_bid
                flags = flags if flags != None else self.test_flags

                # Run the test with the given bid, flags, and result
                self.run_bid_test(image_name, bid, flags, bid_error)
