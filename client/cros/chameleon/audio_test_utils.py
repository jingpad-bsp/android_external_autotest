# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the test utilities for audio tests using chameleon."""

# TODO (cychiang) Move test utilities from chameleon_audio_helpers
# to this module.

import logging
import multiprocessing

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


def bluetooth_nodes_plugged(audio_facade):
    """Checks bluetooth nodes are plugged.

    @param audio_facade: A RemoteAudioFacade to access audio functions on
                         Cros device.

    @raises: error.TestFail if either input or output bluetooth node is
             not plugged.

    """
    curr_out_nodes, curr_in_nodes = audio_facade.get_plugged_node_types()
    return 'BLUETOOTH' in curr_out_nodes and 'BLUETOOTH' in curr_in_nodes


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


_BOARDS_WITH_DEDICATED_HDMI = ['panther']

def has_dedicated_hdmi(host):
    """Checks if the Cros device has a dedicated HDMI output plugged.

    @param host: The CrosHost object.

    @returns: True if Cros device has HDMI plugged. False otherwise.

    """
    board_name = _get_board_name(host)
    if board_name in _BOARDS_WITH_DEDICATED_HDMI:
        logging.info('Board %s has HDMI plugged.', board_name)
        return True
    return False


def suspend_resume(host, suspend_time_secs, resume_network_timeout_secs=50):
    """Performs the suspend/resume on Cros device.

    @param suspend_time_secs: Time in seconds to let Cros device suspend.
    @resume_network_timeout_secs: Time in seconds to let Cros device resume and
                                  obtain network.
    """
    def action_suspend():
        """Calls the host method suspend."""
        host.suspend(suspend_time=suspend_time_secs)

    boot_id = host.get_boot_id()
    proc = multiprocessing.Process(target=action_suspend)
    logging.info("Suspending...")
    proc.daemon = True
    proc.start()
    host.test_wait_for_sleep(suspend_time_secs / 3)
    logging.info("DUT suspended! Waiting to resume...")
    host.test_wait_for_resume(
            boot_id, suspend_time_secs + resume_network_timeout_secs)
    logging.info("DUT resumed!")
