# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the test utilities for audio tests using chameleon."""

# TODO (cychiang) Move test utilities from chameleon_audio_helpers
# to this module.

import logging

from autotest_lib.client.common_lib import error

def check_audio_nodes(audio_facade, audio_nodes):
    """Checks the node selected by Cros device is correct.

    @param audio_facade: A RemoteAudioFacade to access audio functions on
                         Cros device.

    @param audio_nodes: A tuple (out_audio_nodes, in_audio_nodes) containing
                        expected selected output and input nodes.

    @raises: error.TestFail if the nodes selected by Cros device are not expected.

    """
    curr_out_nodes, curr_in_nodes = audio_facade.get_selected_node_types()
    out_audio_nodes, in_audio_nodes = audio_nodes
    if (in_audio_nodes != None and
        sorted(curr_in_nodes) != sorted(in_audio_nodes)):
        raise error.TestFail('Wrong input node(s) selected %s '
                'instead %s!' % (str(curr_in_nodes), str(in_audio_nodes)))
    if (out_audio_nodes != None and
        sorted(curr_out_nodes) != sorted(out_audio_nodes)):
        raise error.TestFail('Wrong output node(s) selected %s '
                'instead %s!' % (str(curr_out_nodes), str(out_audio_nodes)))


def check_plugged_nodes(audio_facade, audio_nodes):
    """Checks the nodes that are currently plugged on Cros device are correct.

    @param audio_facade: A RemoteAudioFacade to access audio functions on
                         Cros device.

    @param audio_nodes: A tuple (out_audio_nodes, in_audio_nodes) containing
                        expected plugged output and input nodes.

    @raises: error.TestFail if the plugged nodes on Cros device are not expected.

    """
    curr_out_nodes, curr_in_nodes = audio_facade.get_plugged_node_types()
    out_audio_nodes, in_audio_nodes = audio_nodes
    if (in_audio_nodes != None and
        sorted(curr_in_nodes) != sorted(in_audio_nodes)):
        raise error.TestFail('Wrong input node(s) plugged %s '
                'instead %s!' % (str(curr_in_nodes), str(in_audio_nodes)))
    if (out_audio_nodes != None and
        sorted(curr_out_nodes) != sorted(out_audio_nodes)):
        raise error.TestFail('Wrong output node(s) plugged %s '
                'instead %s!' % (str(curr_out_nodes), str(out_audio_nodes)))


def _get_board_name(host):
    """Gets the board name.

    @param host: The CrosHost object.

    @returns: The board name.

    """
    return host.get_board().split(':')[1]


def has_internal_speaker(host):
    """Checks if the Cros device has speaker.

    @param host: The CrosHost object.

    @returns: True if Cros device has internal speaker. False otherwise.

    """
    board_name = _get_board_name(host)
    if host.get_board_type() == 'CHROMEBOX' and board_name != 'stumpy':
        logging.info('Board %s does not have speaker.', board_name)
        return False
    return True


def has_internal_microphone(host):
    """Checks if the Cros device has internal microphone.

    @param host: The CrosHost object.

    @returns: True if Cros device has internal microphone. False otherwise.

    """
    board_name = _get_board_name(host)
    if host.get_board_type() == 'CHROMEBOX':
        logging.info('Board %s does not have internal microphone.', board_name)
        return False
    return True
