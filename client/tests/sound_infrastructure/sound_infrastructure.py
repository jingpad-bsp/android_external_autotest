# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test, utils
import os

class sound_infrastructure(test.test):
    """
    Tests that the expected sound infrastructure is present.

    If a control or file is found to be missing, that would imply that
    the driver has changed, and this will have an impact on the entire
    sound system.

     o Missing control

       Regenerate '/etc/asound.state' for each board which is missing
       the control.

         - Log in to console on device.
         - mount -n -o remount,rw /
         - Set all controls to desired levels.
         - Execute 'alsactl store'.
         - Copy new '/etc/asound.state' from device to correct
           place in source tree.  The correct place should normally
           correspond to the 'audioconfig-board' ebuild file.

       Search for that missing control name in the entire source tree,
       and adjust the sources accordingly.

     o Added control (TODO(thutt): added controls not yet checked)

       Regenerate '/etc/asound.state' for each affected board.

       Validate that sound controls still work on each affected target
       device:

          Volume Up, Volume Down, Mute
          Any UI for controlling AV output

       Notify Chrome developers, if necessary, of new control.
       Notify GTalk developers, if necessary, of new control.

     o Missing file, added file

       I don't know what implications this might have, so use caution
       here and update these instructions in the case that this
       occurs.

       At the very least, verify that everything still functions.

    Before submitting the fixes, test & verify:

     o Sound controls still work on each affected target device

          Volume Up, Volume Down, Mute
          Any UI for controlling AV output

     o I/O devices continue to work

          Headphone,
          Internal Speakers
          HDMI
          Internal Mic

     o Notify Chrome developers, if necessary, of removed control.
     o Notify GTalk developers, if necessary, of removed control.
    """
    version = 1

    codec_info = {
        'ALL': {                # Things common to all sound codecs
            'controls': [ ],
            'files': [
                # TODO(thutt): The 'asound.state' file should
                # eventually be present on all machines.  The
                # 'chromeos-per-session' is currently on some
                # machines, but I'd like to deprecate it, favorably
                # using '/etc/asound.state' instead.  Until it can be
                # sorted out, test for neither file.
                #'/etc/asound.state',
                #'/usr/share/alsa/init/chromeos-per-session',
                '/usr/share/alsa/init/00main',
                '/usr/share/alsa/init/default',
                '/usr/share/alsa/init/hda',
                '/usr/share/alsa/init/help',
                '/usr/share/alsa/init/info',
                '/usr/share/alsa/init/test',
                ]
            },

        'WM8903': {
            'controls': [       # Produced from 'amixer scontrols'
                "'Headphone',0",
                "'Headphone ZC',0",
                "'Speaker',0",
                "'Speaker ZC',0",
                "'Line Out',0",
                "'Line Out ZC',0",
                "'Playback Deemphasis',0",
                "'ADC Companding',0",
                "'ADC Companding Mode',0",
                "'ADC Input',0",
                "'ADC OSR',0",
                "'DAC Companding',0",
                "'DAC Companding Mode',0",
                "'DAC Mono',0",
                "'DAC Mute Mode',0",
                "'DAC OSR',0",
                "'DAC Soft Mute Rate',0",
                "'DACL Sidetone Mux',0",
                "'DACR Sidetone Mux',0",
                "'DRC',0",
                "'DRC Anticlip',0",
                "'DRC Attack Rate',0",
                "'DRC Compressor Slope R0',0",
                "'DRC Compressor Slope R1',0",
                "'DRC Compressor Threshold',0",
                "'DRC Decay Rate',0",
                "'DRC FF Delay',0",
                "'DRC Maximum Gain',0",
                "'DRC Minimum Gain',0",
                "'DRC QR',0",
                "'DRC QR Decay Rate',0",
                "'DRC QR Threshold',0",
                "'DRC Smoothing',0",
                "'DRC Smoothing Hysteresis',0",
                "'DRC Smoothing Threshold',0",
                "'DRC Startup',0",
                "'Digital',0",
                "'Digital Sidetone',0",
                "'HPF',0",
                "'HPF Mode',0",
                "'Int Spk',0",
                "'Left Capture Mux',0",
                "'Left Input Mode Mux',0",
                "'Left Input Mux',0",
                "'Left Input PGA',0",
                "'Left Input PGA Common Mode',0",
                "'Left Inverting Input Mux',0",
                "'Left Output Mixer DACL',0",
                "'Left Output Mixer DACR',0",
                "'Left Output Mixer Left Bypass',0",
                "'Left Output Mixer Right Bypass',0",
                "'Left Playback Mux',0",
                "'Left Speaker Mixer DACL',0",
                "'Left Speaker Mixer DACR',0",
                "'Left Speaker Mixer Left Bypass',0",
                "'Left Speaker Mixer Right Bypass',0",
                "'Right Capture Mux',0",
                "'Right Input Mode Mux',0",
                "'Right Input Mux',0",
                "'Right Input PGA',0",
                "'Right Input PGA Common Mode',0",
                "'Right Inverting Input Mux',0",
                "'Right Output Mixer DACL',0",
                "'Right Output Mixer DACR',0",
                "'Right Output Mixer Left Bypass',0",
                "'Right Output Mixer Right Bypass',0",
                "'Right Playback Mux',0",
                "'Right Speaker Mixer DACL',0",
                "'Right Speaker Mixer DACR',0",
                "'Right Speaker Mixer Left Bypass',0",
                "'Right Speaker Mixer Right Bypass',0",
                ],
            'files': [
                '/dev/snd/by-path',
                '/dev/snd/controlC0',
                '/dev/snd/pcmC0D0c',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/pcmC0D1p',
                '/dev/snd/timer',
                '/proc/asound/card0',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/oss',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/tegraseaboard',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            },

        'ALC271X': {
            'controls': [
                "'Master',0",
                "'PCM',0",
                "'Mic Boost',0",
                "'IEC958',0",
                "'IEC958 Default PCM',0",
                "'Capture',0",
                ],
            'files': [
                "/dev/snd/by-path",
                "/dev/snd/controlC0",
                "/dev/snd/hwC0D0",
                "/dev/snd/pcmC0D0c",
                "/dev/snd/pcmC0D0p",
                "/dev/snd/pcmC0D1p",
                "/dev/snd/timer",
                "/proc/asound/Intel",
                "/proc/asound/card0",
                "/proc/asound/cards",
                "/proc/asound/devices",
                "/proc/asound/hwdep",
                "/proc/asound/oss",
                "/proc/asound/pcm",
                "/proc/asound/seq",
                "/proc/asound/timers",
                "/proc/asound/version",
                ]
            },

        'ALC272': {
            'controls': [
                "'Master',0",
                "'Headphone',0",
                "'Speaker',0",
                "'PCM',0",
                "'Mic',0",
                "'Mic Boost',0",
                "'Capture',0",
                "'Capture',1",
                ],
            'files': [
                '/dev/snd/by-path',
                '/dev/snd/controlC0',
                '/dev/snd/hwC0D0',
                '/dev/snd/pcmC0D0c',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/timer',
                '/proc/asound/Intel',
                '/proc/asound/card0',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/hwdep',
                '/proc/asound/oss',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            }
        }

    def exec_cmd(self, cmd):
        return utils.system(cmd, ignore_status = True)

    def pathname_must_exist(self, pathname):
        if not os.path.exists(pathname):
            raise error.TestError("File missing: '%s'" % (pathname))

    def control_must_exist(self, control):
        if self.exec_cmd("amixer scontrols|grep -e \"%s\"" % (control)) != 0:
            raise error.TestError("Control missing: '%s'" % (control))

    def get_codec(self):
        # When the codec cannot be determined, the whole test cannot
        # proceed.  The unknown codec name must be added to 'codecs'
        # below, and the associated attributes must be put into
        # 'codec_info' above.
        codecs = [ 'ALC272', 'WM8903', 'ALC271X' ]
        for c in codecs:
            if self.exec_cmd("aplay -l|grep -e '%s'" % (c)) == 0:
                return c
        raise error.TestError('Unable to determine sound codec.')

    def validate_files(self, files_list):
        for f in files_list:
            self.pathname_must_exist(f)

    def validate_controls(self, controls_list):
        for c in controls_list:
            self.control_must_exist(c)

    def validate_codec(self, codec):
        self.validate_files(codec['files'])
        self.validate_controls(codec['controls'])

    def run_once(self):
        codec = self.get_codec()
        if codec in self.codec_info:
            self.validate_codec(self.codec_info['ALL'])
            self.validate_codec(self.codec_info[codec])
        else:
            raise error.TestError("No test info for codec '%s'." % (codec))

