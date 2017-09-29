# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import re
import datetime
import logging
import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros import power_cycle_usb_util
from autotest_lib.server.cros.multimedia import remote_facade_factory
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test


DUT_BOARD = 'guado'
LONG_TIMEOUT = 30    # seconds
SHORT_TIMEOUT = 15   # seconds


class enterprise_CFM_DualSpeaker(test.test):
    """Tests the following fuctionality works on CfM enrolled devices:
       1. The state of mute/umute should be sync between CfM and 2 speakers.
       2. The volume of two speakers should be sync to volume set by CfM.
       3. When doing mute/unmute speakers from CfM, 1 remains valid.
       4. When changing volume from CfM, 2 remains valid.
       5. After disconnect/re-connect any speaker 1-4 remain valid.
    """
    version = 1


    def _start_hangout_session(self, hangout):
        """Start a hangout session.
        @raises error.TestFail if it fail to start meeting.
        """
        hangout_name = hangout
        logging.info('Session name: %s', hangout_name)
        logging.info('Now joining session.........')
        try:
            self.cfm_facade.start_new_hangout_session(hangout_name)
        except Exception as e:
            raise error.TestFail(str(e))


    def _end_hangout_session(self):
        """End the current session.
        @raises error.TestFail if it fails to end the current session.
        """
        try:
            self.cfm_facade.end_hangout_session()
        except Exception as e:
            raise error.TestFail(str(e))
        logging.info('Stopping session................')


    def _get_cras_speaker_nodes(self):
        """get node for speakers from cras_test_client.
        @returns the list of nodes for speaker. If device not found, returns [].
        """
        cmd = "cras_test_client --dump_server_info | awk '/Output Devices:/,"\
                "/Output Nodes:/' | grep \""\
                + self.prod + "\"| awk -v N=1 '{print $N}'"
        speaker_nodes = [s.strip().split(':')[0] for s in
                self.client.run_output(cmd).splitlines()]
        return speaker_nodes


    def _get_speaker_amixer_nodes(self):
        """get node for mixer based on arecord.
        @returns the list of nodes for mixer. If device not found, returns [].
        """
        cmd = "arecord -l | grep \"" + self.prod + "\"" \
                " | awk -v N=2 '{print $N}'"
        nodes = [s.strip().split(':')[0] for s in
                self.client.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_default_speakers(self):
        """get node for default speakers from cras_test_client.
        @returns the list of nodes for speaker. If device not found, returns [].
        """
        cmd = "cras_test_client --dump_server_info | awk '/Output Nodes:/," \
                "/Input Devices:/' | grep -E 'USB' | grep '*(default' " \
                "|  awk -v N=2 '{print $N}'"
        speakers = [s.strip().split(':')[0] for s in
                self.client.run_output(cmd).splitlines()]
        return speakers


    def _get_cras_default_mixers(self):
        """get node for default mixers from cras_test_client.
        @returns the list of nodes for speaker. If device not found, returns [].
        """
        cmd = "cras_test_client --dump_server_info | awk '/Input Nodes:/," \
                "/Attached Clients:/' | grep '*' " \
                "|  awk -v N=2 '{print $N}'"
        nodes = [s.strip().split(':')[0] for s in
                self.client.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_mixer_nodes(self):
        """get node for mixers from cras_test_client.
        @returns the list of nodes for mixers. If device not found, returns [].
        """
        cmd = "cras_test_client --dump_server_info | awk '/Input Nodes:/," \
                "/Attached Clients:/' | grep \"" + self.prod + \
                "\"|  awk -v N=2 '{print $N}'"
        nodes = [s.strip().split(':')[0] for s in
                self.client.run_output(cmd).splitlines()]
        return nodes


    def _get_cras_speaker_volume(self, node):
        """get volume for speaker from cras_test_client based on node
        @returns the volume of speaker. If device not found, returns None.
        """
        default = False
        cmd = "cras_test_client --dump_server_info | awk '/Output Nodes:/," \
                "/Input Devices:/' | grep -E 'USB' | grep '*' | grep " \
                + node + ":0 |  awk -v N=3 '{print $N}'"
        volume = [s.strip() for s in
                self.client.run_output(cmd).splitlines()][0]
        return volume


    def _get_mixer_mute_state(self, node):
        """get mute state for speaker from cras_test_client based on node
        @returns True if speakers is muted, else return False.
        """
        cmd = "amixer -c " + node + " | grep \"Mono: Capture\"" \
                + "| awk -v N=6 '{print $N}'"
        mute = [s.strip() for s in
                self.client.run_output(cmd).splitlines()][0]

        if re.search(r"\[(off)\]", mute):
            return  True
        else:
            return False


    def _volume_cfm_sync_for_dual_speakers(self):
        """Check whether volume is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        cfm_volume = self.cfm_facade.get_speaker_volume()
        # There is case where cfm_facade.get_speaker_volume() returns empty string.
        # Script polls volume from App up to 15 seconds or until non-zero value
        # is returned.
        poll_time = 0
        while not cfm_volume and poll_time < SHORT_TIMEOUT:
            cfm_volume = self.cfm_facade.get_speaker_volume()
            time.sleep(1)
            logging.info('Checking volume set by App on CfM: %s', cfm_volume)
            poll_time += 1
        if not cfm_volume:
            logging.info('Volume returned from App is Null')
            return False
        nodes = self._get_cras_default_speakers()
        for _node in nodes:
            cras_volume =  self._get_cras_speaker_volume(_node)
            logging.info('Volume in CfM and cras are sync for '
                    'node %s? cfm: %s, cras: %s',
                     _node, cfm_volume, cras_volume)
            if not int(cfm_volume) == int(cras_volume):
                logging.info('Test _volume_cfm_sync_for_dual_speakers fails'
                        ' for node %s', _node)
                return False
        return True


    def _mute_cfm_sync_for_dual_speakers(self):
        """Check whether mute/unmute is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        cfm_mute = self.cfm_facade.is_mic_muted()
        if cfm_mute:
            logging.info('Mixer is muted from CfM.')
        else:
            logging.info('Mixer is not muted from CfM.')

        nodes = self._get_speaker_amixer_nodes()
        for _node in nodes:
            amixer_mute =  self._get_mixer_mute_state(_node)
            if amixer_mute:
                logging.info('amixer shows mic is muted for node %s.', _node)
            else:
                logging.info('amixer shows mix not muted for node %s', _node)
            if not cfm_mute == amixer_mute:
                logging.info('Test _mute_cfm_sync_for_dual_speakers fails'
                        ' for node %s', _node)
                return False
        return True


    def _cmd_usb_devices(self):
        """Populate data for usb devices based on output of usb-device.
        """
        usb_devices = (self.client.run('usb-devices', ignore_status=True).
                stdout.strip().split('\n\n'))
        usb_data = get_usb_devices._extract_usb_data(
                '\nUSB-Device\n'+'\nUSB-Device\n'.join(usb_devices))
        return usb_data


    def _check_dual_speakers(self):
        """Check whether dual speakers are present.
        @returns True if yes, else retrun False.
        """
        prod = None
        vid, pid = get_usb_devices._get_dual_speaker(self.usb_data).split(':')
        if vid and pid:
            vidpid = "{}:{}".format(vid, pid)
            prod = get_usb_devices._get_device_prod(vidpid)
            return  [vid, pid, prod]
        return None


    def _set_preferred_speaker(self):
        """Set preferred speaker to Dual speaker.
        """
        logging.info('CfM sets preferred speaker to %s.',
                self.prod)
        self.cfm_facade.set_preferred_speaker(self.prod)
        logging.info('PEFERRED speaker set to: {} by CfM.'.
                format(self.cfm_facade.get_preferred_speaker()))
        time.sleep(SHORT_TIMEOUT)
        if not self.prod in self.cfm_facade.get_preferred_speaker():
            logging.info('Dual Speaker: %s should be set to preferred',
                    self.prod)
            raise error.TestFail('Fails to set perferred speaker'
                    ' to dut connected dual speaker.')


    def _set_preferred_mixer(self):
        """Set preferred mixer to Dual speaker.
        """
        logging.info('CfM sets preferred mixer to %s.',
                self.prod)
        self.cfm_facade.set_preferred_mic(self.prod)
        logging.info('PEFERRED mixer set to {} by CfM.'.
                format(self.cfm_facade.get_preferred_mic()))
        time.sleep(SHORT_TIMEOUT)
        if not self.prod in self.cfm_facade.get_preferred_mic():
            logging.info('Dual mixer: %s should be set to preferred.',
                    self.prod, self.cfm_facade.get_preferred_mic())
            raise error.TestFail('Fails to set perferred mixer'
                    ' to dut connected dual speaker.')


    def _test_initialize(self):
        """Test initialization
        1. check connected usb devices
        2. check dual speakers are present
        4. set preferred speaker to Dual speaker.
        5. set preferred mixer to Dual speaker.
        """
        self.usb_data = self._cmd_usb_devices()
        if not self.usb_data:
            raise error.TestFail('No usb devices found on DUT.')
        [self.vid, self.pid, self.prod] = self._check_dual_speakers()
        if not self.prod:
            raise error.TestFail('No dual speakers found on DUT.')
        else:
            logging.info('Two speakers: %s are found.', self.prod)


    def  _set_preferred_speaker_mixer(self):
        """Set preferred speaker and mixer to Dual speaker.
        """
        self._set_preferred_speaker()
        self._set_preferred_mixer()
        time.sleep(SHORT_TIMEOUT)
        default_speakers = self._get_cras_default_speakers()
        cras_speakers = self._get_cras_speaker_nodes()
        if not default_speakers == cras_speakers:
            raise error.TestFail('Dual speakers not set to preferred speaker')
        if not self._get_cras_default_mixers() == self._get_cras_mixer_nodes():
            raise error.TestFail('Dual mixs is not set to preferred speaker')


    def _dual_speaker_sanity(self):
        """
        Check whether volume is sync between dual speakers and CfM
        Check whether mute/unmute is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        volume = self._volume_cfm_sync_for_dual_speakers()
        mute = self._mute_cfm_sync_for_dual_speakers()
        return volume and mute


    def _mute_sync_test(self):
        """
        Mute and unmute speaker from CfM.
        Check whether mute/unmute is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        self.cfm_facade.mute_mic()
        if not self.cfm_facade.is_mic_muted():
            raise error.TestFail('CFM fails to mute mic')
        time.sleep(SHORT_TIMEOUT)
        muted = self._mute_cfm_sync_for_dual_speakers()
        self.cfm_facade.unmute_mic()
        if self.cfm_facade.is_mic_muted():
            raise error.TestFail('CFM fails to unmute mic')
        time.sleep(SHORT_TIMEOUT)
        unmuted = self._mute_cfm_sync_for_dual_speakers()
        return muted and unmuted

    def _volume_sync_test(self):
        """
        Change Volume speaker from CfM.
        Check whether volume is sync between dual speakers and CfM.
        @returns True if yes, else retrun False.
        """
        # Known issue: If test_volume is set to 1, cfm sets volume to 0.
        test_volume = random.randrange(2, 100)
        self.cfm_facade.set_speaker_volume(str(test_volume))
        time.sleep(SHORT_TIMEOUT)
        return self._volume_cfm_sync_for_dual_speakers()


    def run_once(self, host):
        """Runs the test."""
        self.client = host
        self.usb_data = []
        self.vid = []
        self.pid = []
        self.prod = []

        logging.info('Sanity check and initilization:')
        self._test_initialize()
        gpio_list = power_cycle_usb_util.get_target_all_gpio(self.client,
                    DUT_BOARD, self.vid, self.pid)

        if len(set(gpio_list)) == 1:
            raise error.TestFail('Speakers have to be tied to different GPIO.')

        factory = remote_facade_factory.RemoteFacadeFactory(host, no_chrome=True)
        self.cfm_facade = factory.create_cfm_facade()
        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(SHORT_TIMEOUT)
            self.client.servo.set('dut_hub1_rst1', 'off')
            time.sleep(SHORT_TIMEOUT)

        try:
            self.cfm_facade.enroll_device()
            self.cfm_facade.skip_oobe_after_enrollment()
            self.cfm_facade.wait_for_hangouts_telemetry_commands()
        except Exception as e:
            raise error.TestFail(str(e))

        self._set_preferred_speaker_mixer()
        logging.info('1. Check CfM and dual speakers have the same setting after joining meeting:')
        self._start_hangout_session('test_cfm_dual_speaker')
        if not self._dual_speaker_sanity():
            raise error.TestFail('Dual speaker Sanity verification fails.')
        logging.info('1.1 Check CfM and dual microphones have the same setting for Mute/unmute:')
        if not self._mute_sync_test():
            raise error.TestFail('Dual speaker Mute-unmute test'
                    ' verification fails')
        logging.info('1.2 Check CfM and dual Speakers have same volume: ')
        if not self._volume_sync_test():
            raise error.TestFail('Dual speaker volume test verification fails')

        for gpio in gpio_list:
            logging.info('2. Check CfM and speakers have the same setting after flapping speaker:')
            logging.info('Power cycle one of Speaker %s', gpio)
            power_cycle_usb_util.power_cycle_usb_gpio(self.client,
                    gpio, SHORT_TIMEOUT)
            time.sleep(SHORT_TIMEOUT)
            logging.info('2.1. Check CfM and dual speakers have same setting')
            if not self._dual_speaker_sanity():
                raise error.TestFail('Dual speaker Sanity verification'
                        ' fails after disconnect/reconnect speaker')
            logging.info('2.1.1. Check CfM and microphones have same setting for Mute/unmute:')
            if not self._mute_sync_test():
                raise error.TestFail('Dual speaker Mute-unmute test'
                        ' verification fails after disconnect/reconnect speaker')
            logging.info('2.1.2. Check CfM and dual Speakers have same volume:')
            if not self._volume_sync_test():
                raise error.TestFail('Dual speaker volume test verification'
                        ' fails after disconnect/reconnect speaker')

        self._end_hangout_session()

        tpm_utils.ClearTPMOwnerRequest(self.client)