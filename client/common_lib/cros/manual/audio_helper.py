# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Get speaker/microphone status from cras_client_test, /proc/asound and
   atrus.log.
"""

from __future__ import print_function

import logging
import re


NUM_AUDIO_STREAM_IN_MEETING = 3

def get_soundcard_by_name(dut, name, debug):
    """
    Returns the soundcard number of specified soundcard by name.
    @param dut: The handle of the device under test.
    @param name: The name of Speaker
                 For example: 'Hangouts Meet speakermic'
    @returns the soundcard, if no device found returns None.
    """
    soundcard = None
    cmd = "cat /proc/asound/cards | grep \"{}\" | grep USB".format(name)
    try:
        soundcard = dut.run(cmd, ignore_status=True).stdout.strip().split()[0]
    except Exception as e:
        soundcard = None
        logging.info('Fail to execute %s: reason: %s', cmd, str(e))
    if soundcard:
        soundcard = "card{}".format(soundcard)
        if debug:
            logging.info('---audio card %s', soundcard)
    return soundcard

def check_soundcard_by_name(dut, name, debug):
    """
    check soundcard by name exists
    @param dut: The handle of the device under test.
    @param name: The name of Speaker
                 For example: 'Hangouts Meet speakermic'
    @returns: True, None if test passes,
              False, errMsg if test fails
    """
    if get_soundcard_by_name(dut, name, debug):
        return True, None
    else:
        return False, 'Soundcard is not found under /proc/asound/cards.'

def check_audio_stream(dut, is_in_meeting, debug):
    """
    Verify speaker is streaming or not streaming as expected.
    @param dut: The handle of the device under test.
    @is_in_meeting: True if CfM is in meeting, False, if not
    @debug: if True print out more log to stdout.
    @returns: True, None if test passes,
              False, errMsg if test fails
    """
    number_stream = get_number_of_active_streams(dut, debug)
    if is_in_meeting:
       if number_stream  >= NUM_AUDIO_STREAM_IN_MEETING:
           return True, None
       else:
           return False, 'Number of Audio streams is not expected.'
    else:
       if number_stream  <=  NUM_AUDIO_STREAM_IN_MEETING:
           return True, None
       else:
           return False, 'Number of Audio streams is not expected.'

def get_audio_stream_state(dut, soundcard):
    """
    Returns the state of stream0 for specified soundcard.

    @param dut: The handle of the device under test. Should be initialized in
                 autotest.
    @param soundcard: soundcard
                 For example: 'card0'

    @returns the list of state of steam0, "Running" or "Stop"

    """
    stream_state = []
    try:
        cmd = ("cat /proc/asound/%s/stream0 | grep Status | "
               "awk -v N=2 '{print $N}'" % soundcard)
        stream_state = dut.run(cmd, ignore_status=True).stdout.split()
    except Exception as e:
            logging.info('Fail to run cli: %s. Reason: %s', cmd, str(e))
    return stream_state


def check_default_speaker_volume(dut, cfm_facade, debug):
    """Check volume of speaker is the same as expected.
    @param dut: The handle of the device under test.
    @param cfm_facade: the handle of cfm facade
    @param debug: boolean to set to print testing log or not to stdout
    @returns True, None if default speakers have same volume as one read
             from hotrod,
             False, errMsg, otherwise
    """
    expected_volume = int(cfm_facade.get_speaker_volume())
    if expected_volume < 1:
        return False, 'Fails to get speaker volume from Hotrod.'
    nodes = get_nodes_for_default_speakers_cras(dut, debug)
    if not nodes:
        logging.info('---Fail to get node for default speaker.')
        return False, 'Fail to get node for default speaker.'
    for node in nodes:
        cras_volume =  get_speaker_volume_cras(dut, node)
        if debug:
            logging.info('---Volume for default speaker are sync for '
                         'node %s? cfm: %d, cras: %d.'
                         'format(node, expected_volume, cras_volume)')
        if not expected_volume == cras_volume:
            logging.info('---Volume Check Fail for default speaker: '
                         'expected_volume:%d, actual_volume:%d.'
                         'format(expected_volume, cras_volume)')
            return False, ('Volume Check Fail for default speaker: '
                           'expected_volume:%d, actual_volume:%d',
                           '% expected_volume, cras_volume')
    if debug:
        logging.info('---Expected volume: %d, actual: %d',
                     expected_volume, cras_volume)
    return True, None

#### the following funcations are based on output of cras_test_client.
def get_number_of_active_streams(dut, debug):
    """
    Returns the number of active stream.
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.
    @returns the number of active streams.
    """
    cmd = ("cras_test_client --dump_server_info "
           "| grep 'Num active streams:' "
           "| awk -v N=4 '{print $N}'")

    try:
        number_of_streams = int(dut.run(cmd, ignore_status=True).stdout.strip())
    except Exception as e:
        logging.info('Fail to get number of streams.')
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
        return None
    if debug:
        logging.info('---number of audio streaming: %d', number_of_streams)
    return number_of_streams


def get_nodes_for_default_speakers_cras(dut, debug):
    """get node for default speakers from cras_test_client.
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.
    @returns the list of nodes for default speakers. If device not found,
     returns [].
    """
    nodes = []
    cmd = ("cras_test_client --dump_server_info | awk '/Output Nodes:/,"
           "/Input Devices:/'")
    try:
        lines = dut.run(cmd, ignore_status=True).stdout.splitlines()
    except Exception as e:
        logging.info('Fail to get nodes for default speaker.')
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
        return nodes
    for _line in lines:
        match = re.findall(r"(\d+):\d+.*USB\s+\*.*", _line)
        if match:
            nodes.append(match[0])
    if debug:
        logging.info('---found nodes for default speaker %s', nodes)
    return nodes


def get_speaker_for_node_cras(dut, node):
    """get node for default speakers from cras_test_client.
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.

    @returns the list of nodes for default speakers. If device not found,
     returns [].
    """
    cmd = ("cras_test_client --dump_server_info | awk '/Output Devices:/,"
           "/Output Nodes:/' | grep '%s'" % node)

    try:
        line = dut.run(cmd, ignore_status=True).stdout.stripe()
        speaker = re.findall(r"^[0-9]+\s*(.*):\s+USB\s+Audio:", line)[0]
    except Exception as e:
        logging.info('Fail to get nodes for default speaker.')
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
    logging.info('---speaker for %s is %s', node, speaker)
    return speaker


def get_nodes_for_default_microphone_cras(dut):
    """get node for default microphones from cras_test_client.
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.

    @returns the list of nodes for default microphone. If device not found,
     returns [].
    """
    nodes = None
    cmd = ("cras_test_client --dump_server_info | awk '/Input Nodes:/,"
           "/Attached clients:/'")
    try:
        lines = dut.run(cmd, ignore_status=True).stdout.splitlines()
        for _line in lines:
            nodes.append(re.findall(r"(\d+):\d+.*USB\s+\*.*", _line)[0])
    except Exception as e:
        logging.info('Fail to get nodes for default speaker.')
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
    return nodes


def get_microphone_for_node_cras(dut, node):
    """get node for default speakers from cras_test_client.
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.

    @returns the list of nodes for default speakers. If device not found,
     returns [].
    """
    cmd = ("cras_test_client --dump_server_info | awk '/Input Devices:/,"
           "/Input Nodes:/' | grep '%s' " % node)

    try:
        line = dut.run(cmd, ignore_status=True).stdout
        microphone = re.findall(r"10\t(.*):\s+USB\s+Audio:", line)[0]
    except Exception as e:
        logging.info('Fail to get nodes for default speaker.')
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
    logging.info('---mic for %s is %s', node, microphone)
    return microphone


def get_speaker_volume_cras(dut, node):
    """get volume for speaker from cras_test_client based on node
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.
    @param node: The node of Speaker
                 Example cli:
                 cras_test_client --dump_server_info | awk
                 '/Output Nodes:/,/Input Devices:/' |  grep 9:0 |
                 awk -v N=3 '{print $N}'

    @returns the volume of speaker. If device not found, returns None.
    """
    cmd = ("cras_test_client --dump_server_info | awk '/Output Nodes:/,"
           "/Input Devices:/' | grep -E 'USB' | grep '%s':0 "
           "|  awk -v N=3 '{print $N}'" % node)
    try:
        volume = int(dut.run(cmd, ignore_status=True).stdout.strip())
    except Exception as e:
        logging.info('Fail to get volume for node %d.', node)
        logging.info('Fail to execute cli: %s, reason: %s', cmd, str(e))
        return None
    return volume


def check_cras_mic_mute(dut, cfm_facade, debug):
    """
    check microphone is muted or unmuted as expected/.
    @param dut: The handle of the device under test.
    @param cfm_facade:  facade of CfM
    @param ismicmuted: True if muted, False otherwise
    @param debug: variable to set whether to print out test output to stdout
    @returns True, none if test passes
             False, errMsg if test fails
    """
    try:
        ismicmuted = cfm_facade.is_mic_muted()
    except Exception as e:
        logging.info('---Fail to get Mute state for microphone.')
        return False, 'Fail to get Mute state for microphone from Hotrod.'
    actual_muted = get_mic_muted_cras(dut, debug)
    if ismicmuted == actual_muted:
        return True, None
    else:
        if debug:
          if ismicmuted:
              logging.info('Hotrod setting: microphone is muted')
          else:
              logging.info('Hotrod setting: microphone is not muted')
          if actual_muted:
              logging.info('cras setting: microphone is muted')
          else:
              logging.info('cras setting: microphone is not muted')
        return False, 'Microphone is not muted/unmuted as shown in Hotrod.'

def check_is_preferred_speaker(dut, name, debug):
    """
    check preferred speaker is speaker to be tested.
    @param dut: The handle of the device under test.
    @param cfm_facade:  facade of CfM
    @param name: name of speaker
    @param debug: variable to set whether to print out test output to stdout
    @returns True, none if test passes
             False, errMsg if test fails
    """
    node = None
    cmd = ("cras_test_client --dump_server_info | awk "
           "'/Output Devices:/,/Output Nodes:/' "
           "| grep '%s' " % name)
    try:
        output = dut.run(cmd, ignore_status=True).stdout.strip()
    except Exception as e:
        logging.info('WARNING: Fail to find %s in cras_test_client.',
                      name)
        logging.info('Fail to run cli %s:, reason: %s', cmd, str(e))
        return False, 'Fail to run cli %s:, reason: %s'.format(cmd, str(e))
    if debug:
        logging.info('---output = %s', output)
    if output:
        node = output.split()[0]
    default_nodes = get_nodes_for_default_speakers_cras(dut, debug)
    if debug:
        logging.info('---default speaker node is %s', default_nodes)
    if node in default_nodes:
        return True, None
    return False, '%s is not set to preferred speaker.'.format(name)


def check_is_preferred_mic(dut, name, debug):
    """check preferred mic is set to speaker to be tested."""
    cmd = ("cras_test_client --dump_server_info | "
           "awk '/Input Devices/,/Input Nodes/'  | grep '%s' | "
           "awk -v N=1 '{print $N}'" % name)
    if debug:
        logging.info('---cmd = %s',cmd)
    try:
        mic_node = dut.run(cmd, ignore_status=True).stdout.strip()
        if debug:
            logging.info('---mic_node : %s', mic_node)
    except Exception as e:
        logging.info('Fail to execute: %s, reason: %s', cmd, str(e))
        return False, 'Fails to run cli'
    try:
         cmd = ("cras_test_client --dump_server_info | awk '/Input Nodes:/,"
               "/Attached clients:/'  | grep default "
               "| awk -v N=2 '{print $N}'")
         mic_node_default = dut.run(cmd, ignore_status=True).stdout.strip()
         if not mic_node_default:
             cmd = ("cras_test_client --dump_server_info | awk '/Input Nodes:/,"
                   "/Attached clients:/'  | grep '%s' "
                   "| awk -v N=2 '{print $N}'" %name)
             mic_node_default = dut.run(cmd,ignore_status=True).stdout.strip()
         if debug:
             logging.info('---%s',cmd)
             logging.info('---%s', mic_node_default)
    except Exception as e:
         logging.info('Fail to execute: %s, reason: %s', cmd, str(e))
         return False, 'Fails to run cli'
    if debug:
        logging.info('---mic node:%s, default node:%s',
                     mic_node, mic_node_default)
    if mic_node == mic_node_default.split(':')[0]:
        return True,  None
    return False, '%s is not preferred microphone'.format(name)


def get_mic_muted_cras(dut, debug):
    """
    Get the status of mute or unmute for microphone
    @param dut: the handle of CfM under test
    @param debug: Boolean to set whether print test output to stdout or not
    @returns True if mic is muted
             False if mic not not muted
    """
    cmd = 'cras_test_client --dump_server_info | grep "Capture Gain"'
    try:
        microphone_muted = dut.run(cmd, ignore_status=True).stdout.strip()
    except Exception as e:
        logging.info('Fail to execute: %s, reason: %s', cmd, str(e))
        return False, 'Fail to execute: %s, reason: %s'.format(cmd, str(e))
    if debug:
        logging.info('---%s',  microphone_muted)
    if "Muted" in microphone_muted:
       return True
    else:
       return False


def check_speaker_exist_cras(dut, name, debug):
    """
    Check speaker exists in cras.
    @param dut: The handle of the device under test.
    @param name: name of speaker
    @param debug: if True print out more log to stdout.
    @returns: True, None if test passes,
              False, errMsg if test fails
    """
    cmd = ("cras_test_client --dump_server_info | awk "
           "'/Output Devices:/, /Output Nodes:/' "
           "| grep '%s'" % name)
    try:
        speaker = dut.run(cmd, ignore_status=True).stdout.splitlines()[0]
    except Exception as e:
        logging.info('WARNING: Fail to find %s in cras_test_client. \
                     Reason: %s', name, str(e))
        logging.info('Fail to execute cli %s: Reason:%s', cmd, str(e))
        speaker = None
    if debug:
        logging.info('---cmd: %s\n---output = %s', cmd, speaker)
    if speaker:
        return True, None
    return False, 'Fail to execute cli %s: Reason:%s'.format(cmd, str(e))


def check_microphone_exist_cras(dut, name, debug):
    """
    Check microphone exists in cras.
    @param dut: The handle of the device under test.
    @param name: name of speaker
    @param debug: if True print out more log to stdout.
    @returns: True, None if test passes,
              False, errMsg if test fails
    """
    microphone = None
    cmd = ("cras_test_client --dump_server_info | awk "
           "'/Input Devices:/, /Input Nodes:/' "
           "| grep '%s'" % name )
    try:
        microphone = dut.run(cmd, ignore_status=True).stdout.splitlines()[0]
    except Exception as e:
        logging.info('Fail to execute cli %s:, reason: %s', cmd, str(e))
    if debug:
        logging.info('---cmd: %s\n---output = %s', cmd, microphone)
    if microphone:
        return True, None
    return False, 'Fails to find microphone %s'.format(name)

def check_audio_stream(dut, is_in_meet, debug):
    """
    Verify speaker is streaming or not streaming as expected.
    @param dut: The handle of the device under test.
    @is_in_meeting: True if CfM is in meeting, False, if not
    @debug: if True print out more log to stdout.
    @returns: True, None if test passes,
              False, errMsg if test fails
    """
    number_stream = get_number_of_active_streams(dut, debug)
    if is_in_meet:
       if number_stream  >= NUM_AUDIO_STREAM_IN_MEETING:
           return True, None
       else:
           return False, 'Number of Audio streams is not expected.'
    else:
       if number_stream  <=  NUM_AUDIO_STREAM_IN_MEETING:
           return True, None
       else:
           return False, 'Number of Audio streams is not expected.'

