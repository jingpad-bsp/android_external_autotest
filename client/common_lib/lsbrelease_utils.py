# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This module provides helper method to parse /etc/lsb-release file to extract
# various information.

import logging
import re

import common
from autotest_lib.client.cros import constants


def _lsbrelease_search(regex, group_id=0):
    """Searches /etc/lsb-release for a regex match.

    @param regex: Regex to match.
    @param group_id: The group in the regex we are searching for.
                     Default is group 0.

    @returns the string in the specified group if there is a match or None if
             not found.

    @raises IOError if /etc/lsb-release can not be accessed.
    """
    with open(constants.LSB_RELEASE) as lsb_release_file:
        for line in lsb_release_file:
            m = re.match(regex, line)
            if m:
                return m.group(group_id)
    return None


def get_current_board():
    """Return the current board name.

    @return current board name, e.g "lumpy", None on fail.
    """
    return _lsbrelease_search(r'^CHROMEOS_RELEASE_BOARD=(.+)$', group_id=1)


def get_chromeos_release_version():
    """
    @return chromeos version in device under test as string. None on fail.
    """
    return _lsbrelease_search(r'^CHROMEOS_RELEASE_VERSION=(.+)$', group_id=1)


def is_moblab():
    """Return if we are running on a Moblab system or not.

    @return the board string if this is a Moblab device or None if it is not.
    """
    try:
        return _lsbrelease_search(r'.*moblab')
    except IOError as e:
        logging.error('Unable to determine if this is a moblab system: %s', e)