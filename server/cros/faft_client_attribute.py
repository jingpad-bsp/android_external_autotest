# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FAFTClientAttribute(object):
    """Class that tests platform name and gives client machine attributes.

    Class attributes:
      broken_warm_reset: boolean, True if warm_reset GPIO is not supported.
            False otherwise.
      broken_rec_mode: boolean, True if rec_mode GPIO is not supported.
            False otherwise.
      chrome_ec: boolean, True if ec is developed by chrome team.
            False otherwise.
      has_lid: boolean, True if the device has a lid. False otherwise.
      has_keyboard: boolean, True if the device has a built in keyboard.
            False otherwise.
      ec_capability: list, specifies ec capability list.
      gbb_version: float, GBB version.
      wp_voltage: string, specifies write protect pin voltage.
      key_matrix_layout: int, specifies which keyboard layout needs to be used
            for testing.
      key_checker: array of keycodes. Used by FAFTSetup test keyboard_checker
            routine to verify the correct keystrokes.
      key_checker_strict: array of keycodes. Used by FAFTSetup test
            strict_keyboard_checker routine to verify the correct keystrokes.
    """
    version = 1

    # Default settings
    broken_warm_reset = False
    broken_rec_mode = False
    chrome_ec = False
    dark_resume_capable = False
    has_lid = True
    has_keyboard = True
    keyboard_dev = True
    long_rec_combo = False
    ec_capability = list()
    gbb_version = 1.1
    wp_voltage = 'pp1800'
    key_matrix_layout = 0
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

    def __init__(self, platform):
        """Initialized. Set up platform-dependent attributes.

        Args:
          platform: Platform name returned by FAFT client.
        """
        self.platform = platform

        # Set 'broken_warm_reset'
        if platform in ['Parrot', 'Butterfly', 'Stout']:
            self.broken_warm_reset = True

        # Set 'broken_rec_mode' for Stout because it does not have rec_mode GPIO
        if platform in ['Stout']:
            self.broken_rec_mode = True

        # Set 'chrome_ec'
        if platform in ['Falco', 'Link', 'Pit', 'Peppy',
                        'Slippy', 'Snow', 'Spring']:
            self.chrome_ec = True

        # Set 'dark_resume_capable'
        if platform in ['Butterfly', 'Falco', 'Link', 'Parrot', 'Peppy',
                        'Slippy']:
            self.dark_resume_capable = True

        # Set 'has_lid'
        if platform in ['Stumpy', 'Kiev']:
            self.has_lid = False

        # Set 'has_keyboard'
        if platform in ['Stumpy', 'Kiev']:
            self.has_keyboard = False

        # Set 'keyboard_dev'
        if platform in ['Aebl', 'Alex', 'Kaen', 'Kiev', 'Lumpy', 'Mario',
                        'Seaboard', 'Stumpy', 'ZGB']:
            self.keyboard_dev = False

        # Set 'long_rec_combo'
        # TODO(shawnn): Check if this is needed for slippy / falco / peppy.
        if platform in ['Link']:
            self.long_rec_combo = True

        # Set 'ec_capability'
        if platform in ['Falco', 'Link', 'Peppy', 'Slippy']:
            self.ec_capability = ['adc_ectemp', 'battery', 'charging',
                                  'keyboard', 'lid', 'x86', 'thermal',
                                  'usb', 'peci']
            if platform == 'Link':
                self.ec_capability.append('kblight')
        elif platform in ['Pit', 'Snow', 'Spring']:
            self.ec_capability = (['battery', 'keyboard', 'arm'] +
                                  (['lid'] if platform in [
                        'Pit', 'Spring'] else []))

        # Set 'gbb_version'
        if platform in ['Alex', 'Mario', 'ZGB']:
            self.gbb_version = 1.0

        # Set 'wp_voltage'
        if platform in ['Falco', 'Link', 'Peppy', 'Slippy']:
            self.wp_voltage = 'pp3300'

        # Set 'key_matrix_layout'
        if platform in ['Parrot']:
            self.key_matrix_layout = 1
            self.key_checker[4] = [0x47, 'press']
            self.key_checker[5] = [0x47, 'release']

        # Set 'key_matrix_layout'
        if platform in ['Stout']:
            self.key_matrix_layout = 2
            self.key_checker[4] = [0x43, 'press']
            self.key_checker[5] = [0x43, 'release']
