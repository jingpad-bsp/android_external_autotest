# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.server import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.server.cros import gsutil_wrapper


class FingerprintTest(test.test):
    """Base class that sets up helpers for fingerprint tests."""
    version = 1

    _FINGERPRINT_BOARD_NAME_SUFFIX = '_fp'

    # Location of firmware from the build on the DUT
    _FINGERPRINT_BUILD_FW_GLOB = '/opt/google/biod/fw/*_fp*.bin'

    _GENIMAGES_SCRIPT_NAME = 'gen_test_images.sh'
    _GENIMAGES_OUTPUT_DIR_NAME = 'images'

    _TEST_IMAGE_FORMAT_MAP = {
        'TEST_IMAGE_ORIGINAL': '%s.bin',
        'TEST_IMAGE_DEV': '%s.dev',
        'TEST_IMAGE_CORRUPT_FIRST_BYTE': '%s_corrupt_first_byte.bin',
        'TEST_IMAGE_CORRUPT_LAST_BYTE': '%s_corrupt_last_byte.bin',
        'TEST_IMAGE_DEV_RB_ZERO': '%s.dev.rb0',
        'TEST_IMAGE_DEV_RB_ONE': '%s.dev.rb1',
        'TEST_IMAGE_DEV_RB_NINE': '%s.dev.rb9'
    }

    _SERVER_GENERATED_FW_DIR_NAME = 'generated_fw'

    _DUT_TMP_PATH_BASE = '/tmp/fp_test'

    _GOLDEN_RO_FIRMWARE_VERSION_MAP = {
        'nocturne_fp': 'nocturne_fp_v2.2.64-58cf5974e'
    }

    _BIOD_UPSTART_JOB_NAME = 'biod'

    _INIT_ENTROPY_CMD = 'bio_wash --factory_init'

    _CROS_FP_ARG = '--name=cros_fp'
    _ECTOOL_RO_VERSION = 'RO version'
    _ECTOOL_RW_VERSION = 'RW version'
    _ECTOOL_ROLLBACK_BLOCK_ID = 'Rollback block id'
    _ECTOOL_ROLLBACK_MIN_VERSION = 'Rollback min version'
    _ECTOOL_ROLLBACK_VERSION = 'Rollback version'

    @staticmethod
    def _parse_ectool_output(ectool_output):
        """Converts ectool colon delimited output into python dict.

        Example:
        RO version:    nocturne_fp_v2.2.64-58cf5974e
        RW version:    nocturne_fp_v2.2.110-b936c0a3c

        becomes:
        {
          'RO version': 'nocturne_fp_v2.2.64-58cf5974e',
          'RW version': 'nocturne_fp_v2.2.110-b936c0a3c'
        }
        """
        ret = {}
        try:
            for line in ectool_output.strip().split('\n'):
                key = line.split(':', 1)[0].strip()
                val = line.split(':', 1)[1].strip()
                ret[key] = val
        except:
            raise error.TestFail('Unable to parse ectool output: %s'
                                 % ectool_output)
        return ret

    def initialize(self, host, test_dir):
        """Performs initialization."""
        self.host = host
        self.servo = host.servo

        self._validate_compatible_servo_version()

        self.servo.initialize_dut()

        logging.info('HW write protect enabled: %s',
                     self.is_hardware_write_protect_enabled())

        self._biod_running = self.host.upstart_status(
            self._BIOD_UPSTART_JOB_NAME)
        if self._biod_running:
            logging.info('Stopping %s', self._BIOD_UPSTART_JOB_NAME)
            self.host.upstart_stop(self._BIOD_UPSTART_JOB_NAME)

        # create tmp working directory on device (automatically cleaned up)
        self._dut_working_dir = self.host.get_tmp_dir(
            parent=self._DUT_TMP_PATH_BASE)
        logging.info('Created dut_working_dir: %s', self._dut_working_dir)
        self.copy_files_to_dut(test_dir, self._dut_working_dir)

        self._build_fw_file = self.get_build_fw_file()

        gen_script = os.path.abspath(os.path.join(self.autodir,
                                                  'server', 'cros', 'faft',
                                                  self._GENIMAGES_SCRIPT_NAME))
        self._dut_firmware_test_images_dir = \
            self._generate_test_firmware_images(gen_script,
                                                self._build_fw_file,
                                                self._dut_working_dir)
        logging.info('dut_firmware_test_images_dir: %s',
                     self._dut_firmware_test_images_dir)

        self._initialize_test_firmware_image_attrs(
            self._dut_firmware_test_images_dir)

        self._initialize_running_fw_version()
        self._initialize_fw_entropy()

    def cleanup(self):
        """Restores original state."""
        if hasattr(self, '_biod_running') and self._biod_running:
            logging.info('Restarting biod')
            self.host.upstart_restart(self._BIOD_UPSTART_JOB_NAME)

        super(FingerprintTest, self).cleanup()

    def after_run_once(self):
        """Logs which iteration just ran."""
        logging.info('successfully ran iteration %d', self.iteration)

    def _validate_compatible_servo_version(self):
        """Asserts if a compatible servo version is not attached."""
        servo_version = self.servo.get_servo_version()
        logging.info('servo version: %s', servo_version)
        if not servo_version.startswith('servo_v4'):
            raise error.TestFail(
                'These tests have only been tested while using servo v4')

    def _generate_test_firmware_images(self, gen_script, build_fw_file,
                                       dut_working_dir):
        """
        Copies the fingerprint firmware from the DUT to the server running
        the tests, which runs a script to generate various test versions of
        the firmware.

        @return full path to location of test images on DUT
        """
        # create subdirectory under existing tmp dir
        server_tmp_dir = os.path.join(self.tmpdir,
                                      self._SERVER_GENERATED_FW_DIR_NAME)
        os.mkdir(server_tmp_dir)
        logging.info('server_tmp_dir: %s', server_tmp_dir)

        # Copy firmware from device to server
        self.get_files_from_dut(build_fw_file, server_tmp_dir)

        # Run the test image generation script on server
        pushd = os.getcwd()
        os.chdir(server_tmp_dir)
        cmd = ' '.join([gen_script,
                        self.get_fp_board(),
                        os.path.basename(build_fw_file)])
        self.run_server_cmd(cmd)
        os.chdir(pushd)

        # Copy resulting files to DUT tmp dir
        server_generated_images_dir = \
            os.path.join(server_tmp_dir, self._GENIMAGES_OUTPUT_DIR_NAME)
        self.copy_files_to_dut(server_generated_images_dir, dut_working_dir)

        return os.path.join(dut_working_dir, self._GENIMAGES_OUTPUT_DIR_NAME)

    def _initialize_test_firmware_image_attrs(self, dut_fw_test_images_dir):
        """Sets attributes with full path to test images on DUT.

        Example: self.TEST_IMAGE_DEV = /some/path/images/nocturne_fp.dev
        """
        for key, val in self._TEST_IMAGE_FORMAT_MAP.iteritems():
            full_path = os.path.join(dut_fw_test_images_dir,
                                     val % self.get_fp_board())
            setattr(self, key, full_path)

    def _initialize_running_fw_version(self):
        """
        Ensures that the running firmware version matches build version
        and flashes to correct version if it doesn't match.

        RO firmware: original version released at factory
        RW firmware: firmware from current build
        """
        build_rw_firmware_version = self.get_build_rw_firmware_version()
        golden_ro_firmware_version = self.get_golden_ro_firmware_version()
        logging.info('Build RW firmware version: %s', build_rw_firmware_version)
        logging.info('Golden RO firmware version: %s',
                     golden_ro_firmware_version)

        fw_versions_match = self.running_fw_version_matches_given_version(
            build_rw_firmware_version, golden_ro_firmware_version)

        if not fw_versions_match:
            self.flash_rw_ro_firmware(self._build_fw_file)
            if not self.running_fw_version_matches_given_version(
                build_rw_firmware_version, golden_ro_firmware_version):
                raise error.TestFail(
                    'Running firmware version does not match expected version')

    def _initialize_fw_entropy(self):
        """Sets the entropy (key) in FPMCU flash (if not set)."""
        result = self.run_cmd(self._INIT_ENTROPY_CMD)
        if result.exit_status != 0:
            raise error.TestFail('Unable to initialize entropy')

    def get_fp_board(self):
        """Returns name of fingerprint EC."""
        board = self.servo.get_board()
        return board + self._FINGERPRINT_BOARD_NAME_SUFFIX

    def get_build_fw_file(self):
        """Returns full path to build FW file on DUT."""
        ls_cmd = 'ls ' + self._FINGERPRINT_BUILD_FW_GLOB
        result = self.run_cmd(ls_cmd)
        if result.exit_status != 0:
            raise error.TestFail('Unable to find firmware from build on device')
        ret = result.stdout.rstrip()
        logging.info('Build firmware file: %s', ret)
        return ret

    def _get_running_firmware_version(self, fw_type):
        """Returns dict of RW and RO firmware versions."""
        result = self._run_ectool_cmd('version')
        parsed = self._parse_ectool_output(result.stdout)
        if result.exit_status != 0:
            raise error.TestFail('Failed to get firmware version')
        version = parsed.get(fw_type)
        if version is None:
            raise error.TestFail('Failed to get firmware version: ' % fw_type)
        return version

    def get_running_rw_firmware_version(self):
        """Returns running RW firmware version."""
        return self._get_running_firmware_version(self._ECTOOL_RW_VERSION)

    def get_running_ro_firmware_version(self):
        """Returns running RO firmware version."""
        return self._get_running_firmware_version(self._ECTOOL_RO_VERSION)

    def get_golden_ro_firmware_version(self):
        """Returns RO firmware version used in factory."""
        board = self.get_fp_board()
        golden_version = self._GOLDEN_RO_FIRMWARE_VERSION_MAP.get(board)
        if golden_version is None:
            raise error.TestFail('Unable to get golden RO version for board: '
                                 % board)
        return golden_version

    def get_build_rw_firmware_version(self):
        """Returns RW firmware version from build (based on filename)."""
        fw_file = os.path.basename(self._build_fw_file)
        if not fw_file.endswith('.bin'):
            raise error.TestFail('Unexpected filename for RW firmware: '
                                 % fw_file)
        return fw_file[:-4]

    def running_fw_version_matches_given_version(self, rw_version, ro_version):
        """
        Returns True if the running RO and RW firmware versions match the
        provided versions.
        """
        running_rw_firmware_version = self.get_running_rw_firmware_version()
        running_ro_firmware_version = self.get_running_ro_firmware_version()

        logging.info('RW firmware, running: %s, expected: %s',
                     running_rw_firmware_version, rw_version)
        logging.info('RO firmware, running: %s, expected: %s',
                     running_ro_firmware_version, ro_version)

        return (running_rw_firmware_version == rw_version and
                running_ro_firmware_version == ro_version)

    def _download_firmware(self, gs_path, dut_file_path):
        """Downloads firmware from Google Storage bucket."""
        bucket = os.path.dirname(gs_path)
        filename = os.path.basename(gs_path)
        logging.info('Downloading firmware, '
                     'bucket: %s, filename: %s, dest: %s',
                     bucket, filename, dut_file_path)
        gsutil_wrapper.copy_private_bucket(host=self.host,
                                           bucket=bucket,
                                           filename=filename,
                                           destination=dut_file_path)
        return os.path.join(dut_file_path, filename)

    def flash_rw_firmware(self, fw_path):
        """Flashes the RW (read-write) firmware."""
        flash_cmd = os.path.join(self._dut_working_dir,
                                 'flash_fp_rw.sh' + ' ' + fw_path)
        result = self.run_cmd(flash_cmd)
        if result.exit_status != 0:
            raise error.TestFail('Flashing RW firmware failed')

    def flash_rw_ro_firmware(self, fw_path):
        """Flashes *all* firmware (both RO and RW)."""
        self.set_hardware_write_protect(False)
        flash_cmd = 'flash_fp_mcu' + ' ' + fw_path
        logging.info('Running flash cmd: %s', flash_cmd)
        result = self.run_cmd(flash_cmd)
        self.set_hardware_write_protect(True)
        if result.exit_status != 0:
            raise error.TestFail('Flashing RW/RO firmware failed')

    def is_hardware_write_protect_enabled(self):
        """Returns state of hardware write protect."""
        fw_wp_state = self.servo.get('fw_wp_state')
        return fw_wp_state == 'on' or fw_wp_state == 'force_on'

    def set_hardware_write_protect(self, enable):
        """Enables or disables hardware write protect."""
        self.servo.set('fw_wp_state', 'force_on' if enable else 'force_off')

    def get_files_from_dut(self, src, dst):
        """Copes files from DUT to server."""
        logging.info('Copying files from (%s) to (%s).', src, dst)
        self.host.get_file(src, dst, delete_dest=True)

    def copy_files_to_dut(self, src_dir, dst_dir):
        """Copies files from server to DUT."""
        logging.info('Copying files from (%s) to (%s).', src_dir, dst_dir)
        self.host.send_file(src_dir, dst_dir, delete_dest=True)

    def run_server_cmd(self, command, timeout=60):
        """Runs command on server; return result with output and exit code."""
        logging.info('Server execute: %s', command)
        result = utils.run(command, timeout=timeout, ignore_status=True)
        logging.info('exit_code: %d', result.exit_status)
        logging.info('stdout:\n%s', result.stdout)
        logging.info('stderr:\n%s', result.stderr)
        return result

    def run_cmd(self, command, timeout=300):
        """Runs command on the DUT; return result with output and exit code."""
        logging.debug('DUT Execute: %s', command)
        result = self.host.run(command, timeout=timeout, ignore_status=True)
        logging.info('exit_code: %d', result.exit_status)
        logging.info('stdout:\n%s', result.stdout)
        logging.info('stderr:\n%s', result.stderr)
        return result

    def _run_ectool_cmd(self, command):
        """Runs ectool on DUT; return result with output and exit code."""
        cmd = 'ectool ' + self._CROS_FP_ARG + ' ' + command
        result = self.run_cmd(cmd)
        return result

    def run_test(self, test_name, *args):
        """Runs test on DUT."""
        logging.info('Running %s', test_name)
        test_cmd = ' '.join([os.path.join(self._dut_working_dir, test_name)] +
                            list(args))
        logging.info('Test command: %s', test_cmd)
        result = self.run_cmd(test_cmd)
        if result.exit_status != 0:
            raise error.TestFail(test_name + ' failed')
