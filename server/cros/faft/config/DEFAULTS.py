# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Default configuration values for FAFT tests go into this file.

For the ability to override these values on a platform specific basis, please
refer to the config object implementation.
"""


class Values(object):
    """We have a class here to allow for inheritence. This is less important
    defaults, but very helpful for platform overrides.
    """

    broken_warm_reset = False
    broken_rec_mode = False
    chrome_ec = False
    dark_resume_capable = False
    has_lid = True
    has_keyboard = True
    keyboard_dev = True
    rec_button_dev_switch = False
    long_rec_combo = False
    use_u_boot = False
    ec_capability = list()
    gbb_version = 1.1
    wp_voltage = 'pp1800'
    spi_voltage = 'pp1800'
    key_checker = [[0x29, 'press'],
                   [0x32, 'press'],
                   [0x32, 'release'],
                   [0x29, 'release'],
                   [0x28, 'press'],
                   [0x28, 'release']]
    key_checker_strict = [[0x29, 'press'],
                          [0x29, 'release'],
                          [0x32, 'press'],
                          [0x32, 'release'],
                          [0x28, 'press'],
                          [0x28, 'release'],
                          [0x61, 'press'],
                          [0x61, 'release']]

    # Has eventlog support including proper timestamps. (Only for old boards!
    # Never disable this "temporarily, until we get around to implementing it"!)
    has_eventlog = True

    # Delay between power-on and firmware screen
    firmware_screen = 10

    # Delay between power-on and dev screen
    dev_screen = 7

    # Delay between keypresses in firmware screen
    confirm_screen = 3

    # Delay between passing firmware screen and text mode warning screen
    legacy_text_screen = 20

    # The developer screen timeouts fit our spec
    dev_screen_timeout = 30

    # Delay for waiting beep done
    beep = 1

    # Delay of loading the USB kernel
    load_usb = 10

    # Delay between USB plug-out and plug-in
    between_usb_plug = 10

    # Delay for waiting client to shutdown
    shutdown = 30

    # Timeout of confirming DUT shutdown
    shutdown_timeout = 60

    # Delay between EC boot and ChromeEC console functional
    ec_boot_to_console = 1.2

    # Delay between EC boot and pressing power button
    ec_boot_to_pwr_button = 0.5

    # Delay of EC software sync hash calculating time
    software_sync = 6

    # Delay of EC software sync updating EC
    software_sync_update = 2

    # Duration of holding cold_reset to reset device
    hold_cold_reset = 0.1

    # Duration of holding power button to shutdown DUT normally
    hold_pwr_button = 2

    # devserver startup time
    devserver = 10

    # Delay of waiting factory install shim to reset TPM
    install_shim_done = 120

    # Delay for user to power cycle the device
    user_power_cycle = 20

    # Delay after /sbin/shutdown before pressing power button
    powerup_ready = 10
