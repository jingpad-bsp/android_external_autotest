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
         - Set all controls to desired levels.
         - Execute 'alsactl --file /tmp/asound.state store'.
         - Copy new '/tmp/asound.state' from device to correct place
           in source tree.  The correct place should normally
           correspond to the 'audioconfig-board' ebuild file for that
           specific board.

       Search the Chromium OS & Chromium sources for that missing
       control name.  If there are references to that control name,
       adjust the sources as necessary.

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
     o Notify Flash player developers, if necessary, of removed control.
    """
    version = 1

    codec_info = {
        'ALL': {                # Things common to all sound codecs
            'controls': [ ],
            'files': [
                '/etc/asound.state',
                '/usr/share/alsa/init/00main',
                '/usr/share/alsa/init/default',
                '/usr/share/alsa/init/hda',
                '/usr/share/alsa/init/help',
                '/usr/share/alsa/init/info',
                '/usr/share/alsa/init/test',
                ]
            },

        'WM8903': {
            'controls': [       # Produced from 'amixer controls'
                "numid=1,iface=MIXER,name='Left Input PGA Switch'",
                "numid=2,iface=MIXER,name='Left Input PGA Volume'",
                "numid=3,iface=MIXER,name='Left Input PGA Common Mode Switch'",
                "numid=4,iface=MIXER,name='Right Input PGA Switch'",
                "numid=5,iface=MIXER,name='Right Input PGA Volume'",
                "numid=6,iface=MIXER,name='Right Input PGA Common Mode Switch'",
                "numid=7,iface=MIXER,name='ADC OSR'",
                "numid=8,iface=MIXER,name='HPF Switch'",
                "numid=9,iface=MIXER,name='HPF Mode'",
                "numid=10,iface=MIXER,name='DRC Switch'",
                "numid=11,iface=MIXER,name='DRC Compressor Slope R0'",
                "numid=12,iface=MIXER,name='DRC Compressor Slope R1'",
                "numid=13,iface=MIXER,name='DRC Compressor Threshold Volume'",
                "numid=14,iface=MIXER,name='DRC Volume'",
                "numid=15,iface=MIXER,name='DRC Minimum Gain Volume'",
                "numid=16,iface=MIXER,name='DRC Maximum Gain Volume'",
                "numid=17,iface=MIXER,name='DRC Attack Rate'",
                "numid=18,iface=MIXER,name='DRC Decay Rate'",
                "numid=19,iface=MIXER,name='DRC FF Delay'",
                "numid=20,iface=MIXER,name='DRC Anticlip Switch'",
                "numid=21,iface=MIXER,name='DRC QR Switch'",
                "numid=22,iface=MIXER,name='DRC QR Threshold Volume'",
                "numid=23,iface=MIXER,name='DRC QR Decay Rate'",
                "numid=24,iface=MIXER,name='DRC Smoothing Switch'",
                "numid=25,iface=MIXER,name='DRC Smoothing Hysteresis Switch'",
                "numid=26,iface=MIXER,name='DRC Smoothing Threshold'",
                "numid=27,iface=MIXER,name='DRC Startup Volume'",
                "numid=28,iface=MIXER,name='Digital Capture Volume'",
                "numid=29,iface=MIXER,name='ADC Companding Mode'",
                "numid=30,iface=MIXER,name='ADC Companding Switch'",
                "numid=31,iface=MIXER,name='Digital Sidetone Volume'",
                "numid=32,iface=MIXER,name='DAC OSR'",
                "numid=33,iface=MIXER,name='Digital Playback Volume'",
                "numid=34,iface=MIXER,name='DAC Soft Mute Rate'",
                "numid=35,iface=MIXER,name='DAC Mute Mode'",
                "numid=36,iface=MIXER,name='DAC Mono Switch'",
                "numid=37,iface=MIXER,name='DAC Companding Mode'",
                "numid=38,iface=MIXER,name='DAC Companding Switch'",
                "numid=39,iface=MIXER,name='Playback Deemphasis Switch'",
                "numid=40,iface=MIXER,name='Headphone Switch'",
                "numid=41,iface=MIXER,name='Headphone ZC Switch'",
                "numid=42,iface=MIXER,name='Headphone Volume'",
                "numid=43,iface=MIXER,name='Line Out Switch'",
                "numid=44,iface=MIXER,name='Line Out ZC Switch'",
                "numid=45,iface=MIXER,name='Line Out Volume'",
                "numid=46,iface=MIXER,name='Speaker Switch'",
                "numid=47,iface=MIXER,name='Speaker ZC Switch'",
                "numid=48,iface=MIXER,name='Speaker Volume'",
                "numid=49,iface=MIXER,name='Int Spk Switch'",
                "numid=50,iface=MIXER,name='Right Speaker Mixer DACL Switch'",
                "numid=51,iface=MIXER,name='Right Speaker Mixer DACR Switch'",
                "numid=52,iface=MIXER,name='Right Speaker Mixer Left Bypass Switch'",
                "numid=53,iface=MIXER,name='Right Speaker Mixer Right Bypass Switch'",
                "numid=54,iface=MIXER,name='Left Speaker Mixer DACL Switch'",
                "numid=55,iface=MIXER,name='Left Speaker Mixer DACR Switch'",
                "numid=56,iface=MIXER,name='Left Speaker Mixer Left Bypass Switch'",
                "numid=57,iface=MIXER,name='Left Speaker Mixer Right Bypass Switch'",
                "numid=58,iface=MIXER,name='Right Output Mixer DACL Switch'",
                "numid=59,iface=MIXER,name='Right Output Mixer DACR Switch'",
                "numid=60,iface=MIXER,name='Right Output Mixer Left Bypass Switch'",
                "numid=61,iface=MIXER,name='Right Output Mixer Right Bypass Switch'",
                "numid=62,iface=MIXER,name='Left Output Mixer DACL Switch'",
                "numid=63,iface=MIXER,name='Left Output Mixer DACR Switch'",
                "numid=64,iface=MIXER,name='Left Output Mixer Left Bypass Switch'",
                "numid=65,iface=MIXER,name='Left Output Mixer Right Bypass Switch'",
                "numid=66,iface=MIXER,name='Right Playback Mux'",
                "numid=67,iface=MIXER,name='Left Playback Mux'",
                "numid=68,iface=MIXER,name='DACR Sidetone Mux'",
                "numid=69,iface=MIXER,name='DACL Sidetone Mux'",
                "numid=70,iface=MIXER,name='Right Capture Mux'",
                "numid=71,iface=MIXER,name='Left Capture Mux'",
                "numid=72,iface=MIXER,name='ADC Input'",
                "numid=73,iface=MIXER,name='Right Input Mode Mux'",
                "numid=74,iface=MIXER,name='Right Inverting Input Mux'",
                "numid=75,iface=MIXER,name='Right Input Mux'",
                "numid=76,iface=MIXER,name='Left Input Mode Mux'",
                "numid=77,iface=MIXER,name='Left Inverting Input Mux'",
                "numid=78,iface=MIXER,name='Left Input Mux'",
                ],
            'files': [
                '/dev/snd/by-path',
                '/dev/snd/controlC0',
                '/dev/snd/pcmC0D0c',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/pcmC0D1p',
                '/dev/snd/timer',
                '/dev/snd/by-path/platform-tegra-snd-seaboard.0',
                '/proc/asound/card0',
                '/proc/asound/card0/id',
                '/proc/asound/card0/pcm0c',
                '/proc/asound/card0/pcm0c/info',
                '/proc/asound/card0/pcm0c/sub0',
                '/proc/asound/card0/pcm0c/sub0/hw_params',
                '/proc/asound/card0/pcm0c/sub0/info',
                '/proc/asound/card0/pcm0c/sub0/status',
                '/proc/asound/card0/pcm0c/sub0/sw_params',
                '/proc/asound/card0/pcm0p',
                '/proc/asound/card0/pcm0p/info',
                '/proc/asound/card0/pcm0p/sub0',
                '/proc/asound/card0/pcm0p/sub0/hw_params',
                '/proc/asound/card0/pcm0p/sub0/info',
                '/proc/asound/card0/pcm0p/sub0/status',
                '/proc/asound/card0/pcm0p/sub0/sw_params',
                '/proc/asound/card0/pcm1p',
                '/proc/asound/card0/pcm1p/info',
                '/proc/asound/card0/pcm1p/sub0',
                '/proc/asound/card0/pcm1p/sub0/hw_params',
                '/proc/asound/card0/pcm1p/sub0/info',
                '/proc/asound/card0/pcm1p/sub0/status',
                '/proc/asound/card0/pcm1p/sub0/sw_params',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/oss', # TODO(thutt): chromium-os:19340
                '/proc/asound/oss/devices',
                '/proc/asound/oss/sndstat',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/tegraseaboard',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            },

        'ALC271X': {
            'controls': [
                "numid=1,iface=MIXER,name='Master Playback Volume'",
                "numid=2,iface=MIXER,name='Master Playback Switch'",
                "numid=3,iface=MIXER,name='Speaker Playback Switch'",
                "numid=4,iface=MIXER,name='Headphone Playback Switch'",
                "numid=5,iface=MIXER,name='Capture Volume'",
                "numid=6,iface=MIXER,name='Capture Switch'",
                "numid=7,iface=MIXER,name='Mic Boost Volume'",
                "numid=8,iface=MIXER,name='IEC958 Playback Con Mask'",
                "numid=9,iface=MIXER,name='IEC958 Playback Pro Mask'",
                "numid=10,iface=MIXER,name='IEC958 Playback Default'",
                "numid=11,iface=MIXER,name='IEC958 Playback Switch'",
                "numid=12,iface=MIXER,name='IEC958 Default PCM Playback"+\
                  " Switch'",
                "numid=13,iface=MIXER,name='PCM Playback Volume'",
                ],
            'files': [
                "/dev/snd/by-path",
                "/dev/snd/controlC0",
                "/dev/snd/hwC0D0",
                "/dev/snd/pcmC0D0c",
                "/dev/snd/pcmC0D0p",
                "/dev/snd/pcmC0D1p",
                "/dev/snd/timer",
                '/proc/asound/Intel',
                '/proc/asound/card0',
                '/proc/asound/card0/codec#0',
                '/proc/asound/card0/id',
                '/proc/asound/card0/pcm0c',
                '/proc/asound/card0/pcm0c/info',
                '/proc/asound/card0/pcm0c/sub0',
                '/proc/asound/card0/pcm0c/sub0/hw_params',
                '/proc/asound/card0/pcm0c/sub0/info',
                '/proc/asound/card0/pcm0c/sub0/prealloc',
                '/proc/asound/card0/pcm0c/sub0/prealloc_max',
                '/proc/asound/card0/pcm0c/sub0/status',
                '/proc/asound/card0/pcm0c/sub0/sw_params',
                '/proc/asound/card0/pcm0p',
                '/proc/asound/card0/pcm0p/info',
                '/proc/asound/card0/pcm0p/sub0',
                '/proc/asound/card0/pcm0p/sub0/hw_params',
                '/proc/asound/card0/pcm0p/sub0/info',
                '/proc/asound/card0/pcm0p/sub0/prealloc',
                '/proc/asound/card0/pcm0p/sub0/prealloc_max',
                '/proc/asound/card0/pcm0p/sub0/status',
                '/proc/asound/card0/pcm0p/sub0/sw_params',
                '/proc/asound/card0/pcm1p',
                '/proc/asound/card0/pcm1p/info',
                '/proc/asound/card0/pcm1p/sub0',
                '/proc/asound/card0/pcm1p/sub0/hw_params',
                '/proc/asound/card0/pcm1p/sub0/info',
                '/proc/asound/card0/pcm1p/sub0/prealloc',
                '/proc/asound/card0/pcm1p/sub0/prealloc_max',
                '/proc/asound/card0/pcm1p/sub0/status',
                '/proc/asound/card0/pcm1p/sub0/sw_params',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/hwdep',
                # TODO(thutt): Present only after sound played.
                #              Reinstate after this test is testing
                #              playing of sound.
                #'/proc/asound/modules',  # Present only after sound played.
                '/proc/asound/oss', # TODO(thutt): chromium-os:19340
                '/proc/asound/oss/devices',
                '/proc/asound/oss/sndstat',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            },

        'Cirrus Analog': {
            'controls': [
                "numid=1,iface=MIXER,name='Master Playback Switch'",
                "numid=2,iface=MIXER,name='Master Playback Volume'",
                "numid=3,iface=MIXER,name='HP/Speakers Playback Switch'",
                "numid=4,iface=MIXER,name='HP/Speakers Playback Volume'",
                "numid=5,iface=MIXER,name='Speaker Boost Playback Volume'",
                "numid=6,iface=MIXER,name='Capture Switch'",
                "numid=7,iface=MIXER,name='Capture Volume'",
                "numid=8,iface=MIXER,name='Internal Mic Capture Volume'",
                "numid=9,iface=MIXER,name='Internal Mic 1 Capture Volume'",
                "numid=10,iface=MIXER,name='Line Capture Volume'",
                "numid=11,iface=MIXER,name='Capture Source'",
                "numid=12,iface=MIXER,name='IEC958 Playback Con Mask'",
                "numid=13,iface=MIXER,name='IEC958 Playback Pro Mask'",
                "numid=14,iface=MIXER,name='IEC958 Playback Default'",
                "numid=15,iface=MIXER,name='IEC958 Playback Switch'",
                "numid=16,iface=MIXER,name='IEC958 Default PCM Playback Switch'",
                "numid=17,iface=MIXER,name='PCM Playback Volume'",
                ],
            'files': [
                '/dev/snd/by-path',
                '/dev/snd/by-path/pci-0000:00:1b.0',
                '/dev/snd/controlC0',
                '/dev/snd/hwC0D0',
                '/dev/snd/pcmC0D0c',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/pcmC0D1p',
                '/dev/snd/timer',
                '/proc/asound/PCH',
                '/proc/asound/card0',
                '/proc/asound/card0/codec#0',
                '/proc/asound/card0/id',
                '/proc/asound/card0/pcm0c',
                '/proc/asound/card0/pcm0c/info',
                '/proc/asound/card0/pcm0c/sub0',
                '/proc/asound/card0/pcm0c/sub0/hw_params',
                '/proc/asound/card0/pcm0c/sub0/info',
                '/proc/asound/card0/pcm0c/sub0/prealloc',
                '/proc/asound/card0/pcm0c/sub0/prealloc_max',
                '/proc/asound/card0/pcm0c/sub0/status',
                '/proc/asound/card0/pcm0c/sub0/sw_params',
                '/proc/asound/card0/pcm0p',
                '/proc/asound/card0/pcm0p/info',
                '/proc/asound/card0/pcm0p/sub0',
                '/proc/asound/card0/pcm0p/sub0/hw_params',
                '/proc/asound/card0/pcm0p/sub0/info',
                '/proc/asound/card0/pcm0p/sub0/prealloc',
                '/proc/asound/card0/pcm0p/sub0/prealloc_max',
                '/proc/asound/card0/pcm0p/sub0/status',
                '/proc/asound/card0/pcm0p/sub0/sw_params',
                '/proc/asound/card0/pcm1p',
                '/proc/asound/card0/pcm1p/info',
                '/proc/asound/card0/pcm1p/sub0',
                '/proc/asound/card0/pcm1p/sub0/hw_params',
                '/proc/asound/card0/pcm1p/sub0/info',
                '/proc/asound/card0/pcm1p/sub0/prealloc',
                '/proc/asound/card0/pcm1p/sub0/prealloc_max',
                '/proc/asound/card0/pcm1p/sub0/status',
                '/proc/asound/card0/pcm1p/sub0/sw_params',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/hwdep',
                '/proc/asound/oss', # TODO(thutt): chromium-os:19340
                '/proc/asound/oss/devices',
                '/proc/asound/oss/sndstat',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/timers',
                '/proc/asound/version',
                ],
            },

        'ALC272': {
            'controls': [
                "numid=1,iface=MIXER,name='Speaker Playback Volume'",
                "numid=2,iface=MIXER,name='Speaker Playback Switch'",
                "numid=3,iface=MIXER,name='Headphone Playback Volume'",
                "numid=4,iface=MIXER,name='Headphone Playback Switch'",
                "numid=5,iface=MIXER,name='Mic Playback Volume'",
                "numid=6,iface=MIXER,name='Mic Playback Switch'",
                "numid=7,iface=MIXER,name='Mic Boost Volume'",
                "numid=8,iface=MIXER,name='Capture Switch'",
                "numid=9,iface=MIXER,name='Capture Switch',index=1",
                "numid=10,iface=MIXER,name='Capture Volume'",
                "numid=11,iface=MIXER,name='Capture Volume',index=1",
                "numid=12,iface=MIXER,name='Master Playback Volume'",
                "numid=13,iface=MIXER,name='Master Playback Switch'",
                "numid=14,iface=MIXER,name='PCM Playback Volume'",
                ],
            'files': [
                    '/dev/snd/by-path',
                    '/dev/snd/by-path/pci-0000:00:1b.0',
                    '/dev/snd/controlC0',
                    '/dev/snd/hwC0D0',
                    '/dev/snd/pcmC0D0c',
                    '/dev/snd/pcmC0D0p',
                    '/dev/snd/timer',
                    '/proc/asound/Intel',
                    '/proc/asound/card0',
                    '/proc/asound/card0/codec#0',
                    '/proc/asound/card0/id',
                    '/proc/asound/card0/pcm0c',
                    '/proc/asound/card0/pcm0c/info',
                    '/proc/asound/card0/pcm0c/sub0',
                    '/proc/asound/card0/pcm0c/sub0/hw_params',
                    '/proc/asound/card0/pcm0c/sub0/info',
                    '/proc/asound/card0/pcm0c/sub0/prealloc',
                    '/proc/asound/card0/pcm0c/sub0/prealloc_max',
                    '/proc/asound/card0/pcm0c/sub0/status',
                    '/proc/asound/card0/pcm0c/sub0/sw_params',
                    '/proc/asound/card0/pcm0p',
                    '/proc/asound/card0/pcm0p/info',
                    '/proc/asound/card0/pcm0p/sub0',
                    '/proc/asound/card0/pcm0p/sub0/hw_params',
                    '/proc/asound/card0/pcm0p/sub0/info',
                    '/proc/asound/card0/pcm0p/sub0/prealloc',
                    '/proc/asound/card0/pcm0p/sub0/prealloc_max',
                    '/proc/asound/card0/pcm0p/sub0/status',
                    '/proc/asound/card0/pcm0p/sub0/sw_params',
                    '/proc/asound/cards',
                    '/proc/asound/devices',
                    '/proc/asound/hwdep',
                    '/proc/asound/oss',  # TODO(thutt): chromium-os:19340
                    '/proc/asound/oss/devices',
                    '/proc/asound/oss/sndstat',
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
        if self.exec_cmd("amixer controls|grep -e \"%s\"" % (control)) != 0:
            raise error.TestError("Control missing: '%s'" % (control))

    def get_codec(self):
        # When the codec cannot be determined, the whole test cannot
        # proceed.  The unknown codec name must be added to 'codecs'
        # below, and the associated attributes must be put into
        # 'codec_info' above.
        codecs = [ 'ALC272',       # Mario, Alex
                   'WM8903',       # Seaboard, Aebl, Kaen, Asymptote
                   'ALC271X',      # ZGB
                   'Cirrus Analog' # Stumpy
                 ]
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
