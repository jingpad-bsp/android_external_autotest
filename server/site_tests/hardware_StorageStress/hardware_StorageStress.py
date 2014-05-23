# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from functools import partial
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server import hosts
from autotest_lib.server import test

class hardware_StorageStress(test.test):
    """
    Integrity stress test for storage device
    """
    version = 1

    # Define default value for the test case
    _TEST_GAP = 60 # 1 min
    _TEST_DURATION = 12 * 60 * 60 # 12 hours
    _SUSPEND_DURATION = 60 * 60 # 1 hour.
    _FIO_REQUIREMENT_FILE = '8k_async_randwrite'
    _FIO_WRITE_FLAGS = []
    _FIO_VERIFY_FLAGS = ['--verifyonly']

    def run_once(self, client_ip, gap=_TEST_GAP, duration=_TEST_DURATION,
                 power_command='reboot', storage_test_command='integrity',
                 suspend_duration=_SUSPEND_DURATION, storage_test_argument=''):
        """
        Run the Storage stress test
        Use hardwareStorageFio to run some test_command repeatedly for a long
        time. Between each iteration of test command, run power command such as
        reboot or suspend.

        @param client_ip:     string of client's ip address (required)
        @param gap:           gap between each test (second) default = 1 min
        @param duration:      duration to run test (second) default = 12 hours
        @param power_command: command to do between each test Command
                              possible command: reboot / suspend / nothing
        @param storage_test_command:  FIO command to run
                              - integrity:  Check data integrity
                              - full_write: Check performance consistency
                                            for full disk write. Use argument
                                            to determine which disk to write
        @param suspend_duration: if power_command is suspend, how long the DUT
                              is suspended.
        """

        # init test
        if not client_ip:
            error.TestError("Must provide client's IP address to test")

        self._client = hosts.create_host(client_ip)
        self._client_at = autotest.Autotest(self._client)
        self._results = {}
        self._suspend_duration = suspend_duration

        # parse power command
        if power_command == 'nothing':
            power_func = self._do_nothing
        elif power_command == 'reboot':
            power_func = self._do_reboot
        elif power_command == 'suspend':
            power_func = self._do_suspend
        else:
            raise error.TestFail(
                'Test failed with error: Invalid power command')

        # parse test command
        if storage_test_command == 'integrity':
            setup_func = self._write_data
            loop_func = self._verify_data
        elif storage_test_command == 'full_write':
            setup_func = self._do_nothing
            loop_func = partial(self._full_disk_write,
                                dev=storage_test_argument)
        else:
            raise error.TestFail('Test failed with error: Invalid test command')

        setup_func()

        # init statistic variable
        min_time_per_loop = self._TEST_DURATION
        max_time_per_loop = 0
        all_loop_time = 0
        avr_time_per_loop = 0
        self._loop_count = 0

        start_time = time.time()

        while time.time() - start_time < duration:
            # sleep
            time.sleep(gap)

            self._loop_count += 1

            # do power command & verify data & calculate time
            loop_start_time = time.time()
            power_func()
            loop_func()
            loop_time = time.time() - loop_start_time

            # update statistic
            all_loop_time += loop_time
            min_time_per_loop = min(loop_time, min_time_per_loop)
            max_time_per_loop = max(loop_time, max_time_per_loop)

        if self._loop_count > 0:
            avr_time_per_loop = all_loop_time / self._loop_count

        logging.info(str('check data count: %d' % self._loop_count))

        # report result
        self.write_perf_keyval({'loop_count':self._loop_count})
        self.write_perf_keyval({'min_time_per_loop':min_time_per_loop})
        self.write_perf_keyval({'max_time_per_loop':max_time_per_loop})
        self.write_perf_keyval({'avr_time_per_loop':avr_time_per_loop})

    def _do_nothing(self):
        pass

    def _do_reboot(self):
        """
        Reboot host machine
        """
        self._client.reboot()

    def _do_suspend(self):
        """
        Suspend host machine
        """
        self._client.suspend(suspend_time=self._suspend_duration)

    def _check_client_test_result(self, client):
        """
        Check result of the client test.
        Auto test will store results in the file named status.
        We check that the second to last line in that file begin with 'END GOOD'

        @ return True if last test passed, False otherwise.
        """
        client_result_dir = '%s/results/default' % client.autodir
        command = 'tail -2 %s/status | head -1' % client_result_dir
        status = client.run(command).stdout.strip()
        logging.info(status)
        return status[:8] == 'END GOOD'

    def _write_data(self):
        """
        Write test data to host using hardware_StorageFio
        """
        logging.info('_write_data')
        result_dir = 'hardware_StorageFio_write'
        self._client_at.run_test('hardware_StorageFio', wait=0,
                                 results_dir=result_dir,
                                 requirements=[(self._FIO_REQUIREMENT_FILE,
                                                self._FIO_WRITE_FLAGS)])
        passed = self._check_client_test_result(self._client)
        if not passed:
            raise error.TestFail('Test failed with error: Data Write Error')

    def _verify_data(self):
        """
        Vertify test data using hardware_StorageFio
        """
        logging.info(str('_verify_data #%d' % self._loop_count))
        result_dir = str('hardware_StorageFio_verify_%d'
                                       % self._loop_count)
        self._client_at.run_test('hardware_StorageFio', wait=0,
                                 results_dir=result_dir,
                                 requirements=[(self._FIO_REQUIREMENT_FILE,
                                                self._FIO_VERIFY_FLAGS)])
        passed = self._check_client_test_result(self._client)
        if not passed:
            raise error.TestFail('Test failed with error: Data Verify #%d Error'
                % self._loop_count)

    def _full_disk_write(self, dev):
        """
        Do the root device full area write and report performance
        """
        logging.info(str('_full_disk_write #%d' % self._loop_count))
        logging.info(str('target device "%s"' % dev))

        # check sanity of target device: begin with /dev/ and can find with ls
        if dev[0:5] != '/dev/':
            raise error.TestFail(
                'Test failed with error: device should begin with /dev/')

        # This command return 0 when device exist, return 2 otherwise
        cmd = 'ls %s >/dev/null 2>&1' % dev
        if self._client.run(cmd, ignore_status=True).exit_status:
            raise error.TestFail(
                'Test failed with error: device does not exist')

        # log some hardware status in the first run
        if self._loop_count == 1:
            cmd = 'cat /sys/class/block/%s/device/type' % dev[5:]
            type = self._client.run(cmd).stdout.strip()
            if type == '0': #scsi disk
                cmd = 'smartctl -x %s' % dev
                logging.info(self._client.run(cmd, ignore_status=True).stdout)
            elif type == 'MMC':
                for field in ['cid', 'csd', 'name', 'serial']:
                    cmd = 'cat /sys/block/%s/device/%s' % (dev[5:], field)
                    result = self._client.run(cmd).stdout.strip()
                    logging.info(str('%s: %s' % (field, result)))
            else:
                raise error.TestFail('Unknown device type')

        # determine current boot device
        cur_dev = self._client.run('rootdev -s -d').stdout.strip()
        logging.info(str('current boot device "%s"' % cur_dev))

        if dev == cur_dev:
            raise error.TestFail(
                'Test failed with error: can not test boot device')

        result_dir = str('hardware_StorageFio_full_disk_write_%d'
                                       % self._loop_count)
        self._client_at.run_test('hardware_StorageFio', dev=dev, filesize=0,
                                 results_dir=result_dir,
                                 requirements=[('64k_stress', [])])

        passed = self._check_client_test_result(self._client)
        if not passed:
            raise error.TestFail(
                "Test failed with error: Full disk Write #%d Error"
                % self._loop_count)
