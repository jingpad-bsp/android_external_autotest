# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FAFTDelayConstants(object):
    """Class that contains the delay constants for FAFT."""
    version = 1

    DEFAULT_DELAY = {
        # Delay between power-on and firmware screen
        'firmware_screen': 10,
        # Delay between passing firmware screen and text mode warning screen
        'legacy_text_screen': 20,
        # The developer screen timeouts fit our spec
        'dev_screen_timeout': 30,
        # Delay for waiting beep done
        'beep': 1,
        # Delay of loading the USB kernel
        'load_usb': 10,
        # Delay between USB plug-out and plug-in
        'between_usb_plug': 10,
        # Delay after running the 'sync' command
        'sync': 5,
        # Delay for waiting client to shutdown
        'shutdown': 30,
        # Delay for waiting client to return before sending EC reboot command
        'ec_reboot_cmd': 1,
        # Delay between EC boot and ChromeEC console functional
        'ec_boot_to_console': 0.5,
        # Delay between EC boot and pressing power button
        'ec_boot_to_pwr_button': 0.5,
        # Delay of EC software sync hash calculating time
        'software_sync': 6,
        # Duration of holding cold_reset to reset device
        'hold_cold_reset': 0.1,
        # devserver startup time
        'devserver': 10,
        # Delay of waiting factory install shim to reset TPM
        'install_shim_done': 120,
    }

    def __init__(self, platform=None):
        """Initialized.

        Args:
          platform: Optional, platform name returned by FAFT client. If not
                    given, use the default delay values.
        """
        self.__dict__.update(self.DEFAULT_DELAY)
        if platform:
            self.__dict__.update(self._get_platform_delay(platform))


    def _get_platform_delay(self, platform):
        """Return platform-specific delay values."""
        setting = dict()

        # Add the platform-specific delay values here.

        return setting
