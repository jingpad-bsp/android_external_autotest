#!/usr/bin/env python
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""library functions to prepare a DUT for lab deployment.

This library will be shared between Autotest and Skylab DUT deployment tools.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server import hosts
from autotest_lib.server import site_utils as server_utils
from autotest_lib.server.hosts import host_info
from autotest_lib.server.hosts import servo_host


_FIRMWARE_UPDATE_TIMEOUT = 600


def create_host(hostname, board, model, servo_hostname, servo_port,
                servo_serial=None):
    """Create a server.hosts.CrosHost object to use for DUT preparation.

    This object contains just enough inventory data to be able to prepare the
    DUT for lab deployment. It does not contain any reference to AFE / Skylab so
    that DUT preparation is guaranteed to be isolated from the scheduling
    infrastructure.

    @param hostname:        FQDN of the host to prepare.
    @param board:           The autotest board label for the DUT.
    @param model:           The autotest model label for the DUT.
    @param servo_hostname:  FQDN of the servo host controlling the DUT.
    @param servo_port:      Servo host port used for the controlling servo.
    @param servo_serial:    (Optional) Serial number of the controlling servo.

    @return a server.hosts.Host object.
    """
    labels = [
            'board:%s' % board,
            'model:%s' % model,
    ]
    attributes = {
            servo_host.SERVO_HOST_ATTR: servo_hostname,
            servo_host.SERVO_PORT_ATTR: servo_port,
    }
    if servo_serial is not None:
        attributes[servo_host.SERVO_SERIAL_ATTR] = servo_serial

    store = host_info.InMemoryHostInfoStore(info=host_info.HostInfo(
            labels=labels,
            attributes=attributes,
    ))
    machine_dict = {
            'hostname': hostname,
            'host_info_store': store,
            'afe_host': server_utils.EmptyAFEHost(),
    }
    host = hosts.create_host(machine_dict)
    servo = servo_host.ServoHost(
            **servo_host.get_servo_args_for_host(host))
    _prepare_servo(servo)
    host.set_servo_host(servo)
    return host


def download_image_to_servo_usb(host, build):
    """Download the given image to the USB attached to host's servo.

    @param host   A server.hosts.Host object.
    @param build  A Chrome OS version string for the build to download.
    """
    host.servo.image_to_servo_usb(host.stage_image_for_servo(build))


def flash_firmware_using_servo(host):
    """Flash DUT firmware directly using servo.

    Rather than running `chromeos-firmwareupdate` on DUT, we can flash DUT
    firmware directly using servo (run command `flashrom`, etc. on servo). In
    this way, we don't require DUT to be in dev mode and with dev_boot_usb
    enabled."""
    host.firmware_install(build=host.get_cros_repair_image_name())


def _start_firmware_update(host, force, result_file):
    """Run `chromeos-firmwareupdate` in background.

    In scenario servo v4 type C, some boards of DUT may lose ethernet
    connectivity on firmware update. There's no way to bring it back except
    rebooting the system.

    @param host         Host instance to use for servo and ssh operations.
    @param force        Boolean value determining if firmware install is forced.
    @param result_file  Path on DUT to save operation logs.

    @returns The process id."""
    fw_update_cmd = 'chromeos-firmwareupdate --mode=factory'
    if force:
        fw_update_cmd += ' --force'

    cmd = [
        "date > %s" % result_file,
        "nohup %s &>> %s" % (fw_update_cmd, result_file),
        "/usr/local/bin/hooks/check_ethernet.hook"
    ]
    return host.run_background(';'.join(cmd))


def _wait_firmware_update_process(host, pid, timeout=_FIRMWARE_UPDATE_TIMEOUT):
    """Wait `chromeos-firmwareupdate` to finish.

    @param host     Host instance to use for servo and ssh operations.
    @param pid      The process ID of `chromeos-firmwareupdate`.
    @param timeout  Maximum time to wait for firmware updating.
    """
    try:
        utils.poll_for_condition(
            lambda: host.run('ps -f -p %s' % pid, timeout=20).exit_status,
            exception=Exception(
                    "chromeos-firmwareupdate (pid: %s) didn't complete in %s "
                    'seconds.' % (pid, timeout)),
            timeout=_FIRMWARE_UPDATE_TIMEOUT,
            sleep_interval=10,
        )
    except error.AutoservRunError:
        # We lose the connectivity, so the DUT should be booting up.
        if not host.wait_up(timeout=host.USB_BOOT_TIMEOUT):
            raise Exception(
                    'DUT failed to boot up after firmware updating.')


def _check_firmware_update_result(host, result_file):
    """Check if firmware updating is good or not.

    @param host         Host instance to use for servo and ssh operations.
    @param result_file  Path of the file saving output of
                        `chromeos-firmwareupdate`.
    """
    fw_update_was_good = ">> DONE: Firmware updater exits successfully."
    result = host.run('cat %s' % result_file)
    if result.stdout.rstrip().rsplit('\n', 1)[1] != fw_update_was_good:
        raise Exception("chromeos-firmwareupdate failed!")


def install_firmware(host, force):
    """Install dev-signed firmware after removing write-protect.

    At start, it's assumed that hardware write-protect is disabled,
    the DUT is in dev mode, and the servo's USB stick already has a
    test image installed.

    The firmware is installed by powering on and typing ctrl+U on
    the keyboard in order to boot the test image from USB.  Once
    the DUT is booted, we run a series of commands to install the
    read-only firmware from the test image.  Then we clear debug
    mode, and shut down.

    @param host   Host instance to use for servo and ssh operations.
    @param force  Boolean value determining if firmware install is forced.
    """
    servo = host.servo
    # First power on.  We sleep to allow the firmware plenty of time
    # to display the dev-mode screen; some boards take their time to
    # be ready for the ctrl+U after power on.
    servo.get_power_state_controller().power_off()
    servo.switch_usbkey('dut')
    servo.get_power_state_controller().power_on()
    time.sleep(10)
    # Dev mode screen should be up now:  type ctrl+U and wait for
    # boot from USB to finish.
    servo.ctrl_u()
    if not host.wait_up(timeout=host.USB_BOOT_TIMEOUT):
        raise Exception('DUT failed to boot in dev mode for '
                        'firmware update')
    # Disable software-controlled write-protect for both FPROMs, and
    # install the RO firmware.
    for fprom in ['host', 'ec']:
        host.run('flashrom -p %s --wp-disable' % fprom,
                 ignore_status=True)

    fw_update_log = '/mnt/stateful_partition/home/root/cros-fw-update.log'
    pid = _start_firmware_update(host, force, fw_update_log)
    _wait_firmware_update_process(host, pid)
    _check_firmware_update_result(host, fw_update_log)

    # Get us out of dev-mode and clear GBB flags.  GBB flags are
    # non-zero because boot from USB was enabled.
    host.run('/usr/share/vboot/bin/set_gbb_flags.sh 0',
             ignore_status=True)
    host.run('crossystem disable_dev_request=1',
             ignore_status=True)
    host.halt()


def install_test_image(host):
    """Install the test image for the given build to DUT.

    This function assumes that the required image is already downloaded onto the
    USB key connected to the DUT via servo.

    @param host   servers.host.Host object.
    """
    host.servo_install()


def _prepare_servo(servo):
    """Prepare servo connected to host for installation steps.

    @param servo  A server.hosts.ServoHost object.
    """
    # Stopping `servod` on the servo host will force `repair()` to
    # restart it.  We want that restart for a few reasons:
    #   + `servod` caches knowledge about the image on the USB stick.
    #     We want to clear the cache to force the USB stick to be
    #     re-imaged unconditionally.
    #   + If there's a problem with servod that verify and repair
    #     can't find, this provides a UI through which `servod` can
    #     be restarted.
    servo.run('stop servod PORT=%d' % servo.servo_port,
              ignore_status=True)
    servo.repair()

    # Don't timeout probing for the host usb device, there could be a bunch
    # of servos probing at the same time on the same servo host.  And
    # since we can't pass None through the xml rpcs, use 0 to indicate None.
    if not servo.get_servo().probe_host_usb_dev(timeout=0):
        raise Exception('No USB stick detected on Servo host')
