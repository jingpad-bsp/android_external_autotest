# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FAFTDelayConstants(object):
    """Class that contains the delay constants for FAFT."""
    version = 1

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
    # Delay after running the 'sync' command
    sync = 2
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

    def __init__(self, platform=None):
        """Initialized.

        Args:
          platform: Optional, platform name returned by FAFT client. If not
                    given, use the default delay values.
        """
        if platform:
            self._update_platform_delay(platform)


    def _update_platform_delay(self, platform):
        """Set platform dependent delay."""

        # Add the platform-specific delay values here.

        if platform == 'Link':
            self.firmware_screen = 7
            self.dev_screen = 4

        if platform == 'Snow':
            self.ec_boot_to_console = 0.4

        if platform == 'Parrot':
            # Parrot uses UART to switch to rec mode instead of gpio thus to
            # clear rec_mode, devices needs to be sufficiently booted.
            self.ec_boot_to_console = 4

            # Parrot takes slightly longer to get to dev screen.
            self.dev_screen = 8

        if platform == 'Spring':
            self.software_sync_update = 6

        if platform in ['Falco', 'Peppy', 'Slippy']:
            # Measured boot-to-console as ~110ms, so this is safe
            self.ec_boot_to_console = 0.6
