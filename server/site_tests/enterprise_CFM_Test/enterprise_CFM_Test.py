# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
import logging
import time
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.cfm import cfm_base_test
from autotest_lib.client.common_lib.cros.manual import audio_helper
from autotest_lib.client.common_lib.cros.manual import cfm_helper
from autotest_lib.client.common_lib.cros.manual import meet_helper
from autotest_lib.client.common_lib.cros.manual import video_helper
from autotest_lib.client.common_lib.cros.manual import get_usb_devices

ATRUS = "18d1:8001"
CORE_DIR_LINES = 3
NUM_AUDIO_STREAM_IN_MEETING = 3
LOG_CHECK_LIST = ['check_kernel_errorlog',
                  'check_video_errorlog',
                  'check_audio_errorlog',
                  'check_chrome_errorlog',
                  'check_atrus_errorlog',
                  'check_usb_stability']


class enterprise_CFM_Test(cfm_base_test.CfmBaseTest):
    """Executes multiple tests on CFM device based on control file,
    after each test, perform mulitple verifications based on control
    file. Test flow can be controlled by control file, such as abort
    on failure, or continue on failure.
    """
    version = 1

    def gpio_test(self):
        """
        Powercycle USB port on Guado.
        """
        if self.run_meeting_test:
            if self.random:
                min_meetings = random.randrange(0, self.gpio_min_meets)
            else:
                min_meetings = self.gpio_min_meets
            if self.meets_last_gpio <=  min_meetings:
                if self.debug:
                    logging.info('\n\nSkip reboot CfM test')
                return True, None
        if cfm_helper.check_is_platform(self.client, 'guado', self.debug):
            status, errmsg =  cfm_helper.gpio_usb_test(self.client,
                              self.gpio_list,
                              self.puts, self.gpio_pause,
                              'guado', self.debug)
            self.gpio_no += 1
            self.meets_last_gpio = 0
        else:
            logging.info('Skip gpio_test for non-guado CfM.')
            return True, None

        ## workaround for bug b/69261543
        if self.isinmeet:
            self.iscameramuted = self.cfm_facade.is_camera_muted()
        return status, errmsg


    def meeting_test(self):
        """
        Join/leave meeting.
        """
        if self.isinmeet:
            status, errmsg = meet_helper.leave_meeting(self.cfm_facade,
                             self.is_meeting, self.debug)
            if status:
                self.iscameramuted = True
                self.isinmeet = False
                return True, None
            else:
                return False, errmsg
        else:
            status, errmsg = meet_helper.join_meeting(self.cfm_facade,
                             self.is_meeting, self.meeting_code, self.debug)
            if status:
                self.iscameramuted = False
                self.isinmeet = True
                self.meet_no += 1
                self.meets_last_reboot += 1
                self.meets_last_gpio += 1
                return True, None
            else:
                return False, errmsg

    def reboot_test(self):
        """
        Reboot CfM.
        """
        if self.run_meeting_test:
            if self.random:
                min_meetings = random.randrange(0, self.reboot_min_meets)
            else:
                min_meetings = self.reboot_min_meets
            if self.meets_last_reboot <  min_meetings:
                if self.debug:
                    logging.info('\n\nSkip reboot CfM test')
                return True, None
        try:
            self.client.reboot()
            time.sleep(self.reboot_timeout)
        except Exception as e:
            logging.info('Reboot test fails, reason %s.', str(e))
            return False, str(e)
        self.reboot_no += 1
        self.meets_last_reboot = 0
        if 'meeting_test' in self.action_config:
            try:
                self.cfm_facade.restart_chrome_for_cfm()
                if self.is_meeting:
                    self.cfm_facade.wait_for_meetings_telemetry_commands()
                else:
                    self.cfm_facade.wait_for_hangouts_telemetry_commands()
            except Exception as e:
                logging.info('Failure found in telemetry API.')
                return False, str(e)
            if self.isinmeet:
                self.isinmeet = False
                self.meeting_test()
        return True, None

    def restart_chrome_and_meeting(self):
        """
        Restart Chrome and Join/Start meeting if previous state is in meeting.
        """
        try:
            self.cfm_facade.restart_chrome_for_cfm()
            if self.is_meeting:
                self.cfm_facade.wait_for_meetings_telemetry_commands()
            else:
                self.cfm_facade.wait_for_hangouts_telemetry_commands()
        except Exception as e:
            logging.info('Failure found in telemetry API.')
            return False, str(e)
        if self.isinmeet:
            self.isinmeet = False
            self.meeting_test()

    # TODO(mzhuo): Adding resetusb test.
    def reset_usb_test(self):
        """
        Reset USB port
        """
        return True, None

    def mute_unmute_camera_test(self):
        """
        Mute or unmute camera.
        """
        if not self.camera:
            logging.info('Skip mute/unmute camera testing.')
            return True, None
        if self.isinmeet:
            if self.iscameramuted:
                status, errmsg = meet_helper.mute_unmute_camera(
                                 self.cfm_facade, True, self.debug)
                if status:
                    self.iscameramuted = False
                else:
                    return False, errmsg
            else:
                status, errmsg =  meet_helper.mute_unmute_camera(
                                  self.cfm_facade, False, self.debug)
                if status:
                    self.iscameramuted = True
                else:
                    return False, errmsg
        return True, None

    def mute_unmute_mic_test(self):
        """
        Mute or unmute microphone.
        """
        if not self.speaker:
            logging.info('Skip mute/unmute microphone testing.')
            return True, None
        if self.isinmeet:
            if self.ismicmuted:
                status, errmsg =  meet_helper.mute_unmute_mic(self.cfm_facade,
                                  True, self.debug)
                if status:
                    self.ismicmuted = False
                else:
                    return False, errmsg
            else:
                status, errmsg =  meet_helper.mute_unmute_mic(self.cfm_facade,
                                  False, self.debug)
                if status:
                    self.ismicmuted = True
                else:
                    return False, errmsg
        return True, None


    def speaker_volume_test(self):
        """
        Update speaker volume.
        """
        if not self.speaker:
            logging.info('Skip update volume of speaker testing.')
            return True, None
        if self.isinmeet:
            return  meet_helper.speaker_volume_test(self.cfm_facade,
                self.vol_change_step, self.vol_change_mode, self.random,
                self.debug)

    # TODO(mzhuo): Adding test to turn on/off monite.
    def flap_monitor_test(self):
        """
        Connect or disconnect monitor.
        """
        return True, None

    def check_usb_enumeration(self):
        """
        Verify all usb devices which were enumerated originally are enumerated.
        """
        return cfm_helper.check_usb_enumeration(self.client,
                                                self.puts, self.debug)

    def check_usb_inf_init(self):
        """
        Verify all usb devices which were enumerated originally have
        valid interfaces: video interface, audio interface or touch
        interface.
        """
        return cfm_helper.check_usb_interface_initializion(self.client,
               self.puts, self.debug)

    def check_v4l2_interface(self):
        """
        Verify camera has v4l2 file handler created.
        """
        if not self.camera:
            return True, None
        return video_helper.check_v4l2_interface(self.client,
               self.camera, self.name_camera, self.debug)

    def check_audio_card(self):
        """
        Verify speaker/microphone has audip file handler created.
        """
        if not self.speaker:
            return True, None
        return audio_helper.check_soundcard_by_name(self.client,
               self.name_speaker, self.debug)

    def check_cras_speaker(self):
        """
        Verify cras server detects speaker.
        """
        if not self.speaker:
            return True, None
        return audio_helper.check_speaker_exist_cras(self.client,
               self.name_speaker, self.debug)

    def check_cras_mic(self):
        """
        Verify cras server detects microphone.
        """
        if not self.speaker:
            return True, None
        return audio_helper.check_microphone_exist_cras(self.client,
               self.name_speaker, self.debug)

    def check_cras_mic_mute(self):
        """
        Verify cras shows mic muted or unmuted as expected.
        """
        if not self.speaker or not self.isinmeet:
            return True, None
        return audio_helper.check_cras_mic_mute(self.client, self.cfm_facade,
               self.debug)

    def check_cras_pspeaker(self):
        """
        Verify cras shows correct preferred speaker.
        """
        if not self.speaker:
            return True, None
        return  audio_helper.check_is_preferred_speaker(self.client,
                self.name_speaker, self.debug)

    def check_cras_speaker_vol(self):
        """
        Verify cras shows correct volume for speaker.
        """
        if not self.speaker or not self.isinmeet:
            return True, None
        return audio_helper.check_default_speaker_volume(self.client,
               self.cfm_facade, self.debug)

    def check_cras_pmic(self):
        """
        Verify cras shows correct preferred microphone.
        """
        if not self.speaker:
            return True, None
        return  audio_helper.check_is_preferred_mic(self.client,
                self.name_speaker, self.debug)

    # TODO(mzhuo): add verification for preferred camera
    def check_prefer_camera(self):
        """
        Verify preferred camera is correct.
        """
        return True, None

    #TODO(mzhuo): add verification to verify camera is muted or unmuted
    #in video stack in kernel space.
    def check_camera_mute(self):
        """
        Verify camera is muted or unmuted as expected.
        """
        return True, None

    def check_video_stream(self):
        """
        Verify camera is streaming or not streaming as expected.
        """
        if not self.camera:
            return True, None
        return video_helper.check_video_stream(self.client,
               self.iscameramuted, self.camera, self.name_camera, self.debug)

    def check_audio_stream(self):
        """
        Verify speaker is streaming or not streaming as expected.
        """
        if not self.speaker:
            return True, None
        return audio_helper.check_audio_stream(self.client,
               self.isinmeet, self.debug)

    # TODO(mzhuo): Adding verification for speaker in Hotrod App
    def check_hotrod_speaker(self):
        """
        Verify hotrod shows all speakers.
        """
        return True, None

    # TODO(mzhuo): Adding verification for mic in Hotrod App
    def check_hotrod_mic(self):
        """
        Verify hotrod shows all microphone.
        """
        return True, None

    # TODO(mzhuo): Adding verification for camera in Hotrod App
    def check_hotrod_camera(self):
        """
        Verify hotrod shows all cameras.
        """
        return True, None

     # TODO(mzhuo): Adding verification for speaker in Hotrod App
    def check_hotrod_pspeaker(self):
        """
        Verify hotrod selects correct preferred speaker.
        """
        return True, None

    # TODO(mzhuo): Adding verification for mic in Hotrod App
    def check_hotrod_pmic(self):
        """
        Verify hotrod selects correct preferred microphone.
        """
        return True, None


    # TODO(mzhuo): Adding verification for camera in Hotrod App
    def check_hotrod_pcamera(self):
        """
        Verify hotrod selects correct preferred camera.
        """
        return True, None

    #TODO(mzhuo): Adding verififaction in hotrod layer for speaker volume
    def check_hotrod_speaker_vol(self):
        """
        Verify hotrod can set volume for speaker.
        """
        return True, None

    #TODO(mzhuo): Adding verififaction in hotrod layer for mic mute status
    def check_hotrod_mic_state(self):
        """
        Verify hotrod can mute or unmute microphone.
        """
        return True, None

    #TODO(mzhuo): Adding verififaction in hotrod layer for camera status
    def check_hotrod_camera_state(self):
        """
        Verify hotrod can mute or unmute camera.
        """
        return True, None

    def check_kernel_errorlog(self):
        """
        Check /var/log/message does not contain any element in
        error_key_words['kernel'].
        """
        return cfm_helper.check_log(self.client, self.log_checking_point,
                                    self.errorlog, 'kernel',
                                    'messages', self.debug)

    def check_chrome_errorlog(self):
        """
        Check /var/log/chrome/chrome does not contain any element in
        error_key_words['chrome'].
        """
        return cfm_helper.check_log(self.client, self.log_checking_point,
                                    self.errorlog, 'chrome',
                                    'chrome', self.debug)

    def check_atrus_errorlog(self):
        """
        Check /var/log/atrus.log does not contain any element in
        error_key_words['atrus'].
        """
        if self.speaker is not ATRUS:
            return True, None
        if cfm_helper.check_is_platform(self.client, 'guado', self.debug):
            return cfm_helper.check_log(self.client, self.log_checking_point,
                                        self.errorlog, 'atrus',
                                        'atrus', self.debug)

    def check_video_errorlog(self):
        """
        Check /var/log/message does not contain any element in
        error_key_words['video'].
        """
        return cfm_helper.check_log(self.client, self.log_checking_point,
                                    self.errorlog, 'video',
                                    'messages', self.debug)

    def check_audio_errorlog(self):
        """
        Check /var/log/message does not contain any element in
        error_key_words['audio'].
        """
        return cfm_helper.check_log(self.client, self.log_checking_point,
                                    self.errorlog, 'audio',
                                    'messages', self.debug)

    def check_usb_errorlog(self):
        """
        Check /var/log/message does not contain any element in
        error_key_words['usb'].
        """
        return cfm_helper.check_log(self.client, self.log_checking_point,
               self.errorlog, 'usb', 'messages', self.debug)

    def check_usb_stability(self):
        """
        Check if no disruptive test done, USB device should not go offline.
        """
        if self.current_test in ['gpio_test', 'reboot_test', 'resetusb_test']:
            return True, None
        return cfm_helper.check_log(self.client, self.log_checking_point,
                                    self.errorlog,
                                    'usb_stability', 'messages', self.debug)

    def check_process_crash(self):
        """
        check no process crashing.
        """
        return cfm_helper.check_process_crash(self.client,
               self.cdlines, self.debug)

    #TODO(mzhuo): Adding verififaction to check whether there is kernel panic
    def check_kernel_panic(self):
        """
        Check no kernel panic reported.
        """
        return True, None

    def initialize_action_check_config(self, action_config, verification_config,
                                       fixedmode):
        """
        Initialize action list based on control file.
        @param action_config: dict defines the number of test should be done
                              for each test
        @param fixedmode: if True all tests are executed in fixed order;
                     if False all tests are executed in random order.
        """
        self.action_config =  []
        if action_config['meeting_test'] == 1:
            self.action_config = ['meeting_test']
        if not self.camera:
            action_config['mute_unmute_camera_test'] = 0
            verification_config['check_v4l2_interface'] = False
            verification_config['check_video_stream'] = False
            verification_config['check_video_errorlog'] = False
        if not self.speaker:
            action_config['mute_unmute_mic_test'] = 0
            action_config['speaker_volume_test']  = 0
            verification_config['check_audio_card'] = False
            verification_config['check_cras_speaker'] = False
            verification_config['check_cras_mic'] = False
            verification_config['check_cras_pspeaker'] = False
            verification_config['check_cras_pmic'] = False
            verification_config['check_audio_stream'] = False
            verification_config['check_audio_errorlog'] = False
            verification_config['check_cras_speaker_vol'] = False
            verification_config['check_cras_mic_mute'] = False


        if fixedmode:
            for action, nof_times in action_config.iteritems():
                if not action == 'meeting_test':
                    self.action_config.extend(nof_times * [action])
        else:
            for action, nof_times in action_config.iteritems():
                if not action == 'meeting_test':
                    dup_test = max(1, random.randrange(0, nof_times))
                    for _ in range(dup_test):
                        self.action_config.insert(max(1, random.randrange(-1,
                             len(self.action_config))), action)
        if action_config['meeting_test'] == 1:
            self.action_config.append('meeting_test')
        logging.info('Test list = %s', self.action_config)
        self.verification_config = [v for v in verification_config.keys()
                                    if verification_config[v]]
        logging.info('Verification list = %s', self.verification_config)


    def initialize_test(self, test_config, action_config, verification_config,
                        error_key_words, test_flow_control):
        """
        Initialize the list of tests and verifications;
        and polulate data needed for test:
            USB devices: which can be retrieved from control file or
            automatically detected by script;
            Test loop, meeting mode, meeting code, test flow contro
            variables.
        """
        self.gpio_pause = test_config['gpiopause']
        self.reboot_timeout =  test_config['reboot_timeout']
        self.vol_change_step = test_config['vol_change_step']
        self.vol_change_mode = test_config['vol_change_mode']
        self.gpio_list = test_config['gpio_list']
        self.is_meeting = test_config['is_meeting']
        self.meeting_code = test_config ['meeting_code']
        self.reboot_min_meets = test_config['reboot_after_min_meets']
        self.gpio_min_meets = test_config['gpio_after_min_meets']
        self.run_meeting_test = action_config['meeting_test']
        self.random = test_flow_control['random_mode']
        self.debug = test_flow_control['debug']
        self.errorlog = error_key_words
        if test_config['puts']:
            self.puts = test_config['puts'].split(',')
        else:
            self.puts = None

        if verification_config['check_process_crash']:
            cfm_helper.clear_core_file(self.client)

        self.action_fun = {
            'gpio_test': self.gpio_test,
            'meeting_test': self.meeting_test,
            'reboot_test': self.reboot_test,
            'reset_usb_test': self.reset_usb_test,
            'mute_unmute_camera_test': self.mute_unmute_camera_test,
            'mute_unmute_mic_test': self.mute_unmute_mic_test,
            'speaker_volume_test': self.speaker_volume_test,
            'flap_monitor_test': self.flap_monitor_test
            }
        self.veri_fun = {
            'check_usb_enumeration': self.check_usb_enumeration,
            'check_usb_inf_init': self.check_usb_inf_init,
            'check_v4l2_interface': self.check_v4l2_interface,
            'check_audio_card': self.check_audio_card,
            'check_cras_speaker': self.check_cras_speaker,
            'check_cras_mic': self.check_cras_mic,
            'check_cras_pspeaker': self.check_cras_pspeaker,
            'check_cras_pmic': self.check_cras_pmic,
            'check_cras_speaker_vol': self.check_cras_speaker_vol,
            'check_cras_mic_mute': self.check_cras_mic_mute,
            'check_prefer_camera': self.check_prefer_camera,
            'check_camera_mute': self.check_camera_mute,
            'check_audio_stream': self.check_audio_stream,
            'check_video_stream': self.check_video_stream,
            'check_hotrod_speaker': self.check_hotrod_speaker,
            'check_hotrod_mic': self.check_hotrod_mic,
            'check_hotrod_camera': self.check_hotrod_camera,
            'check_hotrod_pspeaker': self.check_hotrod_pspeaker,
            'check_hotrod_pmic': self.check_hotrod_pmic,
            'check_hotrod_pcamera': self.check_hotrod_pcamera,
            'check_hotrod_speaker_vol': self.check_hotrod_speaker_vol,
            'check_hotrod_mic_state': self.check_hotrod_mic_state,
            'check_hotrod_camera_state': self.check_hotrod_camera_state,
            'check_usb_errorlog': self.check_usb_errorlog,
            'check_kernel_errorlog': self.check_kernel_errorlog,
            'check_video_errorlog': self.check_video_errorlog,
            'check_audio_errorlog': self.check_audio_errorlog,
            'check_chrome_errorlog': self.check_chrome_errorlog,
            'check_atrus_errorlog': self.check_atrus_errorlog,
            'check_usb_stability': self.check_usb_stability,
            'check_process_crash': self.check_process_crash,
            'check_kernel_panic': self.check_kernel_panic
             }

        self.usb_data = []
        self.speaker = None
        self.camera = None
        self.mimo_sis = None
        self.mimo_display = None
        self.isinmeet = False
        self.iscameramuted = True
        self.ismicmuted = False
        self.meets_last_reboot = 0
        self.meets_last_gpio = 0
        self.meet_no = 0
        self.reboot_no = 0
        self.gpio_no = 0
        self.cdlines = CORE_DIR_LINES

        usb_data = cfm_helper.retrieve_usb_devices(self.client)
        if not usb_data:
            raise error.TestFail('Fails to find any usb devices on CfM.')
        peripherals = cfm_helper.extract_peripherals_for_cfm(usb_data,
                      self.debug)
        if not peripherals:
            raise error.TestFail('Fails to find any periphereal on CfM.')
        if not self.puts:
            self.puts = peripherals.keys()
        else:
            if [put for put in self.puts if not put in peripherals.keys()]:
                if self.debug:
                    logging.info('Fails to find target device %s', put)
                raise error.TestFail('Fails to find device')
        for _put in self.puts:
            if _put in get_usb_devices.CAMERA_MAP.keys():
                self.camera = _put
            if _put in get_usb_devices.SPEAKER_MAP.keys():
                self.speaker = _put
        if self.camera:
            self.name_camera = get_usb_devices.get_device_prod(self.camera)
            logging.info('Camera under test: %s %s',
                          self.camera, self.name_camera)
        if self.speaker:
            self.name_speaker = get_usb_devices.get_device_prod(self.speaker)
            logging.info('Speaker under test: %s %s',
                          self.speaker, self.name_speaker)
        if not test_flow_control['skipcfmc']:
            if not cfm_helper.check_peripherals_for_cfm(peripherals):
                logging.info('Sanity Check on CfM fails.')
                raise error.TestFail('Sanity Check on CfM fails.')
        self.ip_addr = cfm_helper.get_mgmt_ipv4(self.client)
        logging.info('CfM %s passes sanity check, will start test.',
                      self.ip_addr)

        self.initialize_action_check_config(action_config,
                                            verification_config, True)

        if list(set(self.verification_config) & set(LOG_CHECK_LIST)):
            self.log_checking_point = cfm_helper.find_last_log(self.client,
                                      self.speaker, self.debug)

    def process_test_result(self, loop_result, loop_no, test_no,
                            failed_tests, failed_verifications,
                            failed_tests_loop,
                            failed_verifications_loop, test_flow_control,
                            test_config, finished_tests_verifications,
                            test_done):
        """
        Proceess test result data, and print out test report.
        @params loop_result: True when all tests and verifications pass,
                             False if any test or verification fails.
        @param loop_no: sequence number of the loop.
        @param test_no: sequence number of the test.
        @param failed_tests: failed tests.
        @param failed_verifications: failed verifications.
        @param failed_tests_loop: failed tests in the loop.
        @param failed_verifications_loop: failed verifications in the loop.
        @param test_flow_control: variable of flow control defined in
                                  control file
        @param test_config: variable of test config defined in control file
        @param finished_tests_verifications: data to keep track number of
               tests and verifications performed.
        @param test_done: True if all loops are done; False otherwose.
        """
        if 'reboot_test' in finished_tests_verifications.keys():
            finished_tests_verifications['reboot_test'] = self.reboot_no
        if not loop_result and not test_done:
            logging.info('\n\nVerification or Test Failed for loop NO:'
                         ' %d, Test: %d', loop_no, test_no)
            if failed_tests_loop:
                logging.info('----- Failed test: %s', failed_tests_loop)
            if failed_verifications_loop:
                logging.info('----- Failed verifications: %s',
                             failed_verifications_loop)
        if self.debug or test_flow_control['report']:
            logging.info('\n\n\n----------------Summary---------------')
            logging.info('---Loop %d, Test: %d, Meet: %d, Reboot: %d, Gpio: %s',
                         loop_no, test_no, self.meet_no, self.reboot_no,
                         self.gpio_no)
            for key in failed_tests.keys():
                logging.info('----Test: %s, Failed times: %d, Total Run: %d',
                           key, failed_tests[key],
                           finished_tests_verifications[key])
            for key in failed_verifications.keys():
                logging.info('----Verification: %s, Failed times: %d,'
                             'Total Run: %d',
                             key, failed_verifications[key],
                             finished_tests_verifications[key])
            if not loop_result:
                if self.debug:
                    time.sleep(test_config['debug_timeout'])
                if test_flow_control['abort_on_failure']:
                    raise error.TestFail('Test or verification failed')

            if self.random:
                time.sleep(random.randrange(0, test_config['loop_timeout']))
            else:
                 time.sleep(test_config['loop_timeout'])

        if not test_done:
            if list(set(self.verification_config) & set(LOG_CHECK_LIST)):
                self.log_checking_point = cfm_helper.find_last_log(self.client,
                                          self.speaker, self.debug)

    def run_once(self, host, run_test_only, test_config, action_config,
                 verification_config,
                 error_key_words, test_flow_control):
        """Runs the test."""
        self.client = host
        self.initialize_test(test_config, action_config, verification_config,
                              error_key_words, test_flow_control)
        test_no = 0
        failed_tests = {}
        failed_verifications = {}
        finished_tests_verifications = {}
        test_failure_reason = []
        verification_failure_reason = []

        for loop_no in xrange(1, test_config['repeat'] + 1):
            logging.info('\n\n=============%s: Test Loop No: %d=============',
                         self.ip_addr, loop_no)
            if self.debug:
                logging.info('Action list: %s', self.action_config)
            for test in self.action_config:
                loop_result = True
                failed_tests_loop = []
                failed_verifications_loop = []
                if not test in finished_tests_verifications.keys():
                    finished_tests_verifications[test] = 1
                else:
                    finished_tests_verifications[test] += 1
                self.current_test = test
                logging.info('\n\nTest is %s.\n', test)
                test_result, test_msg = self.action_fun[test]()
                test_no += 1
                if not test_result:
                    test_failure_reason.append(test_msg)
                    if test_flow_control['recovery_on_fatal_failure']:
                        if "hotrod" in test_msg and "RPC" in test_msg:
                            if self.debug:
                                logging.info('Restart Chrome to recovery.')
                            self.restart_chrome_and_meeting()
                    failed_tests_loop.append(test)
                    loop_result = False
                    if not test in failed_tests.keys():
                        failed_tests[test] = 1
                    else:
                        failed_tests[test] += 1
                    logging.info('\nTest %s fails\n', test)
                    if test_flow_control['debug']:
                        time.sleep(test_config['debug_timeout'])
                    if test_flow_control['abort_on_failure']:
                        raise error.TestFail('Test %s fails.', test)
                if self.random:
                    time.sleep(random.randrange(test_config['min_timeout'],
                                                test_config['action_timeout']))
                else:
                    time.sleep(test_config['min_timeout'])

                for verification in self.verification_config:
                    if not verification in finished_tests_verifications.keys():
                        finished_tests_verifications[verification] = 1
                    else:
                        finished_tests_verifications[verification] += 1

                    logging.info('\nStart verification %s', verification)
                    veri_result, veri_msg = self.veri_fun[verification]()
                    if not veri_result:
                        verification_failure_reason.append(veri_msg)
                        failed_verifications_loop.append(verification)
                        if not verification in failed_verifications.keys():
                            failed_verifications[verification] = 1
                        else:
                            failed_verifications[verification] += 1
                        logging.info('\nVerification %s failed', verification)
                        loop_result = False

                self.process_test_result(loop_result, loop_no, test_no,
                                         failed_tests,
                                         failed_verifications,
                                         failed_tests_loop,
                                         failed_verifications_loop,
                                         test_flow_control,
                                         test_config,
                                         finished_tests_verifications, False)

            if self.random:
                self.initialize_action_check_config(action_config,
                                                    verification_config, True)

        logging.info('\n\n===============Finish==============')
        self.process_test_result(loop_result, loop_no, test_no,
                                 failed_tests,
                                 failed_verifications,
                                 failed_tests_loop,
                                 failed_verifications_loop,
                                 test_flow_control,
                                 test_config,
                                 finished_tests_verifications, True)
        if test_failure_reason:
            logging.info('\nTest failure reason %s', test_failure_reason)
        if verification_failure_reason:
            logging.info('\nVerification failure reason %s',
                         verification_failure_reason)
