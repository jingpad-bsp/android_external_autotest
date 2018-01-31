# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Meeting related operations"""

from __future__ import print_function

import logging
import random
import time


def join_meeting(handler, is_meeting, meet_code, debug):
    """
    Join meeting.
    @param handler: CfM telemetry remote facade,
    @param is_meeting: True, None if CfM running MEET mode,
                       False if CfM running hangout mode
    @param meeting_code: meeting code
    @param debug: if True, None print out status to stdout
    @returns: True, None if CfM joins meeting successfully,
              False otherwise.
    """
    try:
        if is_meeting:
            if debug:
                logging.info('+++start meet meeting')
            if meet_code:
                handler.join_meeting_session(meet_code)
            else:
                logging.info('+++start a new meeting')
                handler.start_meeting_session()
        else:
            if debug:
                logging.info('+++start hangout meeting')
            if meet_code:
                handler.start_new_hangout_session(meet_code)
            else:
                handler.start_hangout_session()
        if debug:
            logging.info('+++Meeting %s joined.', meet_code)
            return True, None
    except Exception as e:
        logging.info('Fail to join meeting %s, reason:%s', meet_code, str(e))
    # temperory workround since the 1st join meeting call fails.
    time.sleep(5)
    try:
        if is_meeting:
            if meet_code:
                handler.join_meeting_session(meet_code)
                logging.info('+++ Retry to join a meeting')
            else:
                logging.info('+++ Retry to start a new meeting')
                handler.start_meeting_session()
            return True, None
    except Exception as e:
        logging.info('Fail to join meeting %s, reason:%s', meet_code, str(e))
        return False, str(e)


def leave_meeting(handler, is_meeting, debug):
    """
    Leave meeting.
    @param handler: CfM telemetry remote facade,
    @param is_meeting: True, None if CfM running MEET mode,
                       False if CfM running hangout mode
    @param debug: if True, None print out status to stdout
    @returns: True, None if CfM leaves meeting successfully,
              False otherwise.

    """
    try:
        if is_meeting:
            handler.end_meeting_session()
        else:
            handler.end_hangout_session()
    except Exception as e:
        logging.info('Fail to leave meeting, reason: %s.', str(e))
        return False, str(e)
    if debug:
        logging.info('+++meet ended')
    return True, None


def mute_unmute_camera(handler, is_muted, debug):
    """
    @param handler: CfM telemetry remote facade,
    @param is_muted: True, None if camera is muted,
                     False otherwise.
    @param debug: if True, None print out status to stdout
    @returns: True, None if camera is muted/unmuted successfully,
              False otherwise.
    """
    try:
        if is_muted:
            if debug:
                logging.info('+++unmute camera')
            handler.unmute_camera()
        else:
            if debug:
                logging.info('+++mute camera')
            handler.mute_camera()
    except Exception as e:
        logging.info('Fail to mute or unmute camera, reason: %s', str(e))
        return False, str(e)
    return True, None


def mute_unmute_mic(handler, is_muted, debug):
    """
    @param handler: CfM telemetry remote facade,
    @param is_muted: True, None if mic is muted,
                     False otherwise.
    @param debug: if True, None print out status to stdout
    @returns: True, None if camera is muted/unmuted successfully,
              False otherwise.
    """
    try:
         if is_muted:
             if debug:
                 logging.info('+++unmute mic')
             handler.unmute_mic()
         else:
             if debug:
                 logging.info('+++mute mic')
             handler.mute_mic()
    except Exception as e:
        logging.info('Fail to mute or unmute mic, reason: %s.', str(e))
        return False, str(e)
    return True, None


def speaker_volume_test(handle, step, mode, randommode, debug):
    """
    Change speaker's volume.
    @param handle: CfM telemetry remote facade,
    @param step: volume to be increased or decreased in one call
    @param mode: if it equal to 1, update volume directly to
                 targeted value,
                 else, update volume in multiple calls.
    @param randommode: if True, None, the value of volume to be change in
                 each call is randomly set,
                 else, the value is fixed defined by step.
    @param debug: if True, None print out test status or output to stdout,
                  else, not print out.
    """
    test_volume = random.randrange(2, 100)
    try:
        if mode == 1:
            handle.set_speaker_volume(test_volume)
            if debug:
                logging.info('+++Set volume to %d', test_volume)
            return test_volume, None
        else:
            step = max(2, step)
            current = int(handle.get_speaker_volume())
            if test_volume > current:
               while test_volume > current:
                   if randommode:
                       transit_volume = current + random.randrange(1, step)
                   else:
                       transit_volume = current + step
                   if transit_volume > test_volume:
                       transit_volume = test_volume

                   handle.set_speaker_volume(transit_volume)
                   current = int(handle.get_speaker_volume())
                   if debug:
                       logging.info('+++set vol %d, current %d, target %d',
                                    transit_volume, current, test_volume)
            else:
               while test_volume < current:
                   if randommode:
                       transit_volume = current - random.randrange(1, step)
                   else:
                       transit_volume = current - step
                   if transit_volume < test_volume:
                       transit_volume = test_volume
                   handle.set_speaker_volume(transit_volume)
                   current = int(handle.get_speaker_volume())
                   if debug:
                       logging.info('+++set vol %d, current %d, target %d',
                                    transit_volume, current, test_volume)

            return current, None
    except Exception as e:
        logging.info('Fail to set speaker volume, reason: %s', str(e))
        return None, str(e)
