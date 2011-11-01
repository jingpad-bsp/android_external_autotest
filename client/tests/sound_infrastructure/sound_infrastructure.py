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
                '/etc/init/adhd.conf', # Upstart script, from ADHD package
                '/etc/asound.state',   # Factory defaults.  From ADHD.
                '/usr/bin/alsamixer',
                '/usr/bin/amixer',
                '/usr/sbin/alsactl',
                '/usr/share/alsa/init/00main',
                '/usr/share/alsa/init/default',
                '/usr/share/alsa/init/hda',
                '/usr/share/alsa/init/help',
                '/usr/share/alsa/init/info',
                '/usr/share/alsa/init/test',
                ]
            },

        'WM8903': {
            'controls': [ ], # Create: amixer controls >WM8903.controls
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
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/tegraseaboard',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            },

        'ALC271X': {
            'controls': [ ], # Create: amixer controls >ALC271X.controls
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
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/timers',
                '/proc/asound/version',
                ]
            },

        'Cirrus Analog': {
            'controls': [ ], # Create: amixer controls >Cirrus_Analog.controls
            'files': [
                '/dev/snd/by-path',
                '/dev/snd/by-path/pci-0000:00:1b.0',
                '/dev/snd/controlC0',
                '/dev/snd/hwC0D0',
                '/dev/snd/hwC0D3',
                '/dev/snd/pcmC0D0c',
                '/dev/snd/pcmC0D0p',
                '/dev/snd/pcmC0D3p',
                '/dev/snd/pcmC0D7p',
                '/dev/snd/pcmC0D8p',
                '/dev/snd/seq',
                '/dev/snd/timer',
                '/proc/asound/PCH',
                '/proc/asound/card0',
                '/proc/asound/cards',
                '/proc/asound/devices',
                '/proc/asound/hwdep',
                '/proc/asound/pcm',
                '/proc/asound/seq',
                '/proc/asound/timers',
                '/proc/asound/version',
                '/proc/asound/card0/codec#0',
                '/proc/asound/card0/codec#3',
                '/proc/asound/card0/eld#3.0',
                '/proc/asound/card0/eld#3.1',
                '/proc/asound/card0/eld#3.2',
                '/proc/asound/card0/id',
                '/proc/asound/card0/pcm0c',
                '/proc/asound/card0/pcm0p',
                '/proc/asound/card0/pcm3p',
                '/proc/asound/card0/pcm7p',
                '/proc/asound/card0/pcm8p',
                '/proc/asound/card0/pcm0c/info',
                '/proc/asound/card0/pcm0c/sub0',
                '/proc/asound/card0/pcm0c/sub0/hw_params',
                '/proc/asound/card0/pcm0c/sub0/info',
                '/proc/asound/card0/pcm0c/sub0/prealloc',
                '/proc/asound/card0/pcm0c/sub0/prealloc_max',
                '/proc/asound/card0/pcm0c/sub0/status',
                '/proc/asound/card0/pcm0c/sub0/sw_params',
                '/proc/asound/card0/pcm0p/info',
                '/proc/asound/card0/pcm0p/sub0',
                '/proc/asound/card0/pcm0p/sub0/hw_params',
                '/proc/asound/card0/pcm0p/sub0/info',
                '/proc/asound/card0/pcm0p/sub0/prealloc',
                '/proc/asound/card0/pcm0p/sub0/prealloc_max',
                '/proc/asound/card0/pcm0p/sub0/status',
                '/proc/asound/card0/pcm0p/sub0/sw_params',
                '/proc/asound/card0/pcm3p/info',
                '/proc/asound/card0/pcm3p/sub0',
                '/proc/asound/card0/pcm3p/sub0/hw_params',
                '/proc/asound/card0/pcm3p/sub0/info',
                '/proc/asound/card0/pcm3p/sub0/prealloc',
                '/proc/asound/card0/pcm3p/sub0/prealloc_max',
                '/proc/asound/card0/pcm3p/sub0/status',
                '/proc/asound/card0/pcm3p/sub0/sw_params',
                '/proc/asound/card0/pcm7p',
                '/proc/asound/card0/pcm7p/sub0/info',
                '/proc/asound/card0/pcm7p/sub0',
                '/proc/asound/card0/pcm7p/sub0/hw_params',
                '/proc/asound/card0/pcm7p/sub0/info',
                '/proc/asound/card0/pcm7p/sub0/prealloc',
                '/proc/asound/card0/pcm7p/sub0/prealloc_max',
                '/proc/asound/card0/pcm7p/sub0/status',
                '/proc/asound/card0/pcm7p/sub0/sw_params',
                '/proc/asound/card0/pcm8p/info',
                '/proc/asound/card0/pcm8p/sub0',
                '/proc/asound/card0/pcm8p/sub0/hw_params',
                '/proc/asound/card0/pcm8p/sub0/info',
                '/proc/asound/card0/pcm8p/sub0/prealloc',
                '/proc/asound/card0/pcm8p/sub0/prealloc_max',
                '/proc/asound/card0/pcm8p/sub0/status',
                '/proc/asound/card0/pcm8p/sub0/sw_params',
                '/proc/asound/seq',
                ],
            },

        'ALC272': {
            'controls': [ ], # Create: amixer controls >ALC272.controls
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

    def get_codec_basename(self, codec):
        return codec.replace(' ', '_')

    def get_data_pathname(self, filename):
        return os.path.join(self.bindir, filename)

    def validate_files(self, files_list):
        for f in files_list:
            self.pathname_must_exist(f)

    def validate_controls(self, controls_list):
        for c in controls_list:
            self.control_must_exist(c)

    def validate_codec(self, codec):
        self.validate_files(codec['files'])
        self.validate_controls(codec['controls'])

    def read_codec_data(self, codec):
        codec_basename = self.get_codec_basename(codec)

        # Read controls which must be present.
        pathname = self.get_data_pathname(codec_basename + ".controls")
        self.codec_info[codec]['controls'] = [line.strip() for line in
                                              open(pathname)]

    def run_once(self):
        codec = self.get_codec()
        self.read_codec_data(codec)
        if codec in self.codec_info:
            self.validate_codec(self.codec_info['ALL'])
            self.validate_codec(self.codec_info[codec])
        else:
            raise error.TestError("No test info for codec '%s'." % (codec))
