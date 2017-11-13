# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import re
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros import power_cycle_usb_util
from autotest_lib.server.cros.cfm import cfm_base_test

# CFMs have a base volume level threshold. Setting the level below 2
# is interpreted by the CFM as 0.
CFM_VOLUME_LEVEL_LOWER_LIMIT = 2
CFM_VOLUME_LEVEL_UPPER_LIMIT = 100
TIMEOUT_SECS  = 10


class enterprise_CFM_DualSpeaker(cfm_base_test.CfmBaseTest):
    """
    Tests that the following functionality works on CfM enrolled devices:

       1. Mixer mute/umute state should be in sync between CfM and 2 speakers.
       2. Volume of two speakers should be in sync with the volume set by CfM.
       3. When muting/unmuting speakers from CfM, #1 still holds.
       4. When changing volume from CfM, #2 still holds.
       5. After disconnect/re-connecting any speaker #1-4 still holds.
    """
    version = 1


    def _get_cras_speaker_nodes(self):
        """
        Gets speaker nodes from the cras_test_client.

        @returns A list of speaker node IDs or [] if no speaker is found.
        """
        cmd = ("cras_test_client --dump_server_info"
               " | awk '/Output Devices:/,/Output Nodes:/'"
               " | grep \"%s\""
               " | awk -v N=1 '{print $N}'" % self._dual_speaker.name)
        speaker_nodes = [s.strip().split(':')[0] for s in
                         self._host.run_output(cmd).splitlines()]
        return speaker_nodes


    def _get_speaker_amixer_nodes(self):
        """
        Gets the speaker mixer (microphone) nodes from arecord.

        @returns A list of mixer node IDs or [] if no mixer is found.
        """
        cmd = ("arecord -l"
               " | grep \"%s\""
               " | awk -v N=2 '{print $N}'" % self._dual_speaker.name)
        nodes = [s.strip().split(':')[0] for s in
                 self._host.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_default_speakers(self):
        """
        Gets the default speakers from cras_test_client.

        @returns A list of speaker node IDs or [] if no speaker is found.
        """
        cmd = ("cras_test_client --dump_server_info"
               " | awk '/Output Nodes:/,/Input Devices:/'"
               " | grep -E 'USB' | grep '*(default' "
               " |  awk -v N=2 '{print $N}'")
        speakers = [s.strip().split(':')[0] for s in
                    self._host.run_output(cmd).splitlines()]
        return speakers


    def _get_cras_default_mixers(self):
        """
        Gets the default mixers from cras_test_client.

        @returns A list of speaker node IDs or [] if no device is found.
        """
        cmd = ("cras_test_client --dump_server_info"
               " | awk '/Input Nodes:/,/Attached Clients:/'"
               " | grep '*' "
               " | awk -v N=2 '{print $N}'")
        nodes = [s.strip().split(':')[0] for s in
                 self._host.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_mixer_nodes(self):
        """
        Gets the mixer nodes from cras_test_client.

        @returns A list of mixer node IDs or [] if no device is found.
        """
        cmd = ("cras_test_client --dump_server_info"
               " | awk '/Input Nodes:/,/Attached Clients:/'"
               " | grep \"%s\""
               " | awk -v N=2 '{print $N}'" % self._dual_speaker.name)
        nodes = [s.strip().split(':')[0] for s in
                 self._host.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_speaker_volume(self, node_id):
        """
        Gets the speaker volume for a node from cras_test_client.

        @param node_id: the node ID to query.
        @returns the volume of speaker. If device not found, returns None.
        """
        cmd = ("cras_test_client --dump_server_info"
               " | awk '/Output Nodes:/,/Input Devices:/'"
               " | grep -E 'USB'"
               " | grep '*'"
               " | grep %s:0 |  awk -v N=3 '{print $N}'" % node_id)
        volume = [s.strip() for s in
                  self._host.run_output(cmd).splitlines()][0]
        return volume


    def _get_mixer_mute_state(self, node_id):
        """
        Gets the speaker mute state from cras_test_client.

        @param node_id: the node to query.
        @returns True if speakers is muted, otherwise False.
        """
        cmd = ("amixer -c %s"
               " | grep \"Mono: Capture\""
               " | awk -v N=6 '{print $N}'" % node_id)
        mute = [s.strip() for s in
                self._host.run_output(cmd).splitlines()][0]

        if re.search(r"\[(off)\]", mute):
            return  True
        else:
            return False


    def _volume_cfm_sync_for_dual_speakers(self):
        """Checks whether volume is synced between dual speakers and CfM."""
        cfm_volume = self.cfm_facade.get_speaker_volume()
        # There is case where cfm_facade.get_speaker_volume() returns empty
        # string. Script polls volume from App up to 15 seconds or until
        # non-zero value is returned.
        poll_time = 0
        while not cfm_volume and poll_time < TIMEOUT_SECS:
            cfm_volume = self.cfm_facade.get_speaker_volume()
            time.sleep(1)
            logging.info('Checking volume set by App on CfM: %s', cfm_volume)
            poll_time += 1
        if not cfm_volume:
            logging.info('Volume returned from App is Null')
            return False
        nodes = self._get_cras_default_speakers()
        for node_id in nodes:
            cras_volume =  self._get_cras_speaker_volume(node_id)
            logging.info('Volume in CfM and cras are sync for '
                    'node %s? cfm: %s, cras: %s',
                     node_id, cfm_volume, cras_volume)
            if not int(cfm_volume) == int(cras_volume):
                logging.error('Test _volume_cfm_sync_for_dual_speakers fails'
                              ' for node %s', node_id)
                return False
        return True


    def _mute_cfm_sync_for_dual_speakers(self):
        """Checks whether mute/unmute is sync between dual speakers and CfM."""
        cfm_mute = self.cfm_facade.is_mic_muted()
        if cfm_mute:
            logging.info('Mixer is muted from CfM.')
        else:
            logging.info('Mixer is not muted from CfM.')

        nodes = self._get_speaker_amixer_nodes()
        for node_id in nodes:
            amixer_mute =  self._get_mixer_mute_state(node_id)
            if amixer_mute:
                logging.info('amixer shows mic is muted for node %s.', node_id)
            else:
                logging.info('amixer shows mix not muted for node %s', node_id)
            if not cfm_mute == amixer_mute:
                logging.error('Test _mute_cfm_sync_for_dual_speakers fails'
                              ' for node %s', node_id)
                return False
        return True


    @property
    def _usb_data(self):
        """Gets the usb_data for currently connected USB devices."""
        usb_devices = (self._host.run('usb-devices', ignore_status=True).
            stdout.strip().split('\n\n'))
        return get_usb_devices._extract_usb_data(
            '\nUSusb_data-Device\n'+'\nUSB-Device\n'.join(usb_devices))


    def _find_dual_speakers(self):
        """
        Finds dual speakers connected to the DUT.

        @returns A UsbDevice representing the dual speaker or None if not found.
        """
        vid_pid = get_usb_devices._get_dual_speaker(self._usb_data)
        if vid_pid:
            return get_usb_devices._get_device_prod(vid_pid)
        else:
            return None


    def _set_preferred_speaker(self, speaker_name):
        """Set preferred speaker to Dual speaker."""
        logging.info('CfM sets preferred speaker to %s.', speaker_name)
        self.cfm_facade.set_preferred_speaker(speaker_name)
        time.sleep(TIMEOUT_SECS)
        current_prefered_speaker = self.cfm_facade.get_preferred_speaker()
        logging.info('Prefered speaker set to %s', current_prefered_speaker)
        if speaker_name != current_prefered_speaker:
            raise error.TestFail('Failed to set prefered speaker! '
                                 'Expected %s, got %s',
                                 speaker_name, current_prefered_speaker)


    def _set_preferred_mixer(self, mixer_name):
        """Set preferred mixer/microphone to Dual speaker."""
        logging.info('CfM sets preferred mixer to %s.', mixer_name)
        self.cfm_facade.set_preferred_mic(mixer_name)
        time.sleep(TIMEOUT_SECS)
        current_prefered_mixer = self.cfm_facade.get_preferred_speaker()
        logging.info('Prefered mixer set to %s by CfM.', current_prefered_mixer)
        if mixer_name != current_prefered_mixer:
            raise error.TestFail('Failed to set prefered mixer! '
                                 'Expected %s, got %s',
                                 mixer_name, current_prefered_mixer)


    def  _set_preferred_speaker_mixer(self):
        """Sets preferred speaker and mixer to Dual speaker."""
        self._set_preferred_speaker(self._dual_speaker.name)
        self._set_preferred_mixer(self._dual_speaker.name)
        time.sleep(TIMEOUT_SECS)
        default_speakers = self._get_cras_default_speakers()
        cras_speakers = self._get_cras_speaker_nodes()
        if default_speakers != cras_speakers:
            raise error.TestFail('Dual speakers not set to preferred speaker')
        if not self._get_cras_default_mixers() == self._get_cras_mixer_nodes():
            raise error.TestFail('Dual mixs is not set to preferred speaker')


    def _dual_speaker_sanity(self):
        """
        Performs a speaker sanity check:
            1. Checks whether volume is sync between dual speakers and CfM
            2. Checks whether mute/unmute is sync between dual speakers and CfM.
        @returns True if passed, otherwise False.
        """
        volume = self._volume_cfm_sync_for_dual_speakers()
        mute = self._mute_cfm_sync_for_dual_speakers()
        return volume and mute


    def _mute_sync_test(self):
        """
        Mutes and unmutes speaker from CfM.
        Check whether mute/unmute is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        self.cfm_facade.mute_mic()
        if not self.cfm_facade.is_mic_muted():
            raise error.TestFail('CFM fails to mute mic')
        time.sleep(TIMEOUT_SECS)
        muted = self._mute_cfm_sync_for_dual_speakers()
        self.cfm_facade.unmute_mic()
        if self.cfm_facade.is_mic_muted():
            raise error.TestFail('CFM fails to unmute mic')
        time.sleep(TIMEOUT_SECS)
        unmuted = self._mute_cfm_sync_for_dual_speakers()
        return muted and unmuted

    def _volume_sync_test(self):
        """
        Changes speaker volume from CfM.
        Checks whether volume is sync between dual speakers and CfM.
        @returns True if check succeeds, otherwise False.
        """
        test_volume = random.randrange(CFM_VOLUME_LEVEL_LOWER_LIMIT,
                                       CFM_VOLUME_LEVEL_UPPER_LIMIT)
        self.cfm_facade.set_speaker_volume(str(test_volume))
        time.sleep(TIMEOUT_SECS)
        return self._volume_cfm_sync_for_dual_speakers()


    def run_once(self):
        """Runs the test."""
        logging.info('Sanity check and initilization:')
        self._dual_speaker = self._find_dual_speakers()
        if not self._dual_speaker:
            raise error.TestFail('No dual speakers found on DUT.')

        # Remove 'board:' prefix.
        board_name = self._host.get_board().split(':')[1]
        gpio_list = power_cycle_usb_util.get_target_all_gpio(
            self._host, board_name, self._dual_speaker.vendor_id,
            self._dual_speaker.product_id)
        if len(set(gpio_list)) == 1:
            raise error.TestFail('Speakers have to be tied to different GPIO.')

        self.cfm_facade.wait_for_hangouts_telemetry_commands()

        self._set_preferred_speaker_mixer()
        logging.info('1. Check CfM and dual speakers have the same setting '
                     'after joining meeting:')
        self.cfm_facade.start_new_hangout_session('test_cfm_dual_speaker')
        if not self._dual_speaker_sanity():
            raise error.TestFail('Dual speaker Sanity verification fails.')

        logging.info('1.1 Check CfM and dual microphones have the same '
                     'setting for Mute/unmute:')
        if not self._mute_sync_test():
            raise error.TestFail('Dual speaker Mute-unmute test'
                    ' verification fails')

        logging.info('1.2 Check CfM and dual Speakers have same volume: ')
        if not self._volume_sync_test():
            raise error.TestFail('Dual speaker volume test verification fails')

        for gpio in gpio_list:

            logging.info('2. Check CfM and speakers have the same setting '
                         'after flapping speaker:')
            logging.info('Power cycle one of Speaker %s', gpio)
            power_cycle_usb_util.power_cycle_usb_gpio(self._host,
                    gpio, TIMEOUT_SECS)
            time.sleep(TIMEOUT_SECS)

            logging.info('2.1. Check CfM and dual speakers have same setting')
            if not self._dual_speaker_sanity():
                raise error.TestFail('Dual speaker Sanity verification'
                        ' fails after disconnect/reconnect speaker')

            logging.info('2.1.1. Check CfM and microphones have same setting '
                         'for Mute/unmute:')
            if not self._mute_sync_test():
                raise error.TestFail(
                    'Dual speaker Mute-unmute test verification fails after '
                    'disconnect/reconnect speaker')

            logging.info('2.1.2. Check CfM and dual Speakers have same volume:')
            if not self._volume_sync_test():
                raise error.TestFail('Dual speaker volume test verification'
                        ' fails after disconnect/reconnect speaker')

        self.cfm_facade.end_hangout_session()
