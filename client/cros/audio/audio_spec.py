# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the test utilities for audio spec."""

_BOARD_TYPE_CHROMEBOX = 'CHROMEBOX'
_BOARD_TYPE_CHROMEBIT = 'CHROMEBIT'
_BOARD_WITHOUT_SOUND_CARD = ['gale', 'veyron_rialto']

def has_internal_speaker(board_type, board_name):
    """Checks if a board has internal speaker.

    @param board_type: board type string. E.g. CHROMEBOX, CHROMEBIT, and etc.
    @param board_name: board name string.

    @returns: True if the board has internal speaker. False otherwise.

    """
    if ((board_type == _BOARD_TYPE_CHROMEBOX and board_name != 'stumpy')
            or board_type == _BOARD_TYPE_CHROMEBIT
            or board_name in _BOARD_WITHOUT_SOUND_CARD):
        return False
    return True


def has_internal_microphone(board_type):
    """Checks if a board has internal microphone.

    @param board_type: board type string. E.g. CHROMEBOX, CHROMEBIT, and etc.

    @returns: True if the board has internal microphone. False otherwise.

    """
    if (board_type == _BOARD_TYPE_CHROMEBOX
            or board_type == _BOARD_TYPE_CHROMEBIT):
        return False
    return True


def has_headphone(board_type):
    """Checks if a board has headphone.

    @param board_type: board type string. E.g. CHROMEBOX, CHROMEBIT, and etc.

    @returns: True if the board has headphone. False otherwise.

    """
    if board_type == _BOARD_TYPE_CHROMEBIT:
        return False
    return True


def has_hotwording(board_name, model_name):
    """Checks if a board has hotwording.

    @param board_name: board name of the DUT.
    @param model_name: model name of the DUT.

    @returns: True if the board has hotwording.

    """
    if board_name in ['coral', 'eve', 'kevin', 'nami', 'pyro', 'samus']:
        return True
    return False
