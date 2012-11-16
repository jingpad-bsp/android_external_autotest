# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class FAFTClientAttribute(object):
    """Class that tests platform name and gives client machine attributes."""
    version = 1

    # Default settings
    broken_warm_reset = False
    chrome_ec = False
    has_lid = True
    has_keyboard = True
    keyboard_dev = True
    long_rec_combo = False
    ec_capability = list()
    wp_voltage = 'pp1800'
    key_matrix_layout = 0

    def __init__(self, platform):
        """Initialized. Set up platform-dependent attributes.

        Args:
          platform: Platform name returned by FAFT client.
        """
        self.platform = platform

        # Set 'broken_warm_reset'
        if platform in ['Parrot', 'Butterfly']:
            self.broken_warm_reset = True

        # Set 'chrome_ec'
        if platform in ['Link', 'Snow']:
            self.chrome_ec = True

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
        if platform in ['Link']:
            self.long_rec_combo = True

        # Set 'ec_capability'
        if platform == 'Link':
            self.ec_capability = ['adc_ectemp', 'battery', 'charging',
                                        'keyboard', 'lid', 'x86', 'thermal',
                                        'usb', 'peci']
        elif platform == 'Snow':
            self.ec_capability = ['battery', 'keyboard', 'arm']

        # Set 'wp_voltage'
        if platform == 'Link':
            self.wp_voltage = 'pp3300'

        # Set 'key_matrix_layout'
        if platform == 'Parrot':
            self.key_matrix_layout = 1
