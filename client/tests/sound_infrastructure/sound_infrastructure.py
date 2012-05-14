# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test, utils
import logging
import os

class sound_infrastructure(test.test):
    """
    Tests that the expected sound infrastructure is present.

    If a file is found to be missing, that would imply that the driver
    has changed, and this will have an impact on the entire sound
    system.

    Before submitting the fixes, test & verify:

     o Sound controls still work on each affected target device

          Volume Up, Volume Down, Mute
          Any UI for controlling AV output

     o I/O devices continue to work

          Headphone,
          Internal Speakers
          HDMI
          Internal Mic

     o To create 'files' data file:

        Execute the following on the DUT:

          tar --absolute-names -c /dev/snd /proc/asound 2>/dev/null| \
            tar -t 2>/dev/null|sed -e 's./$..g' >{codec-name}.files

        {codec-name} should be replaced with the name of the codec.
        Replace spaces in the codec name with '_'.
        See get_codec() to help determine the name of the codec.
    """
    version = 1

    codec_info = {
        'ALL': {                # Things common to all sound codecs
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
            'files'   : [ ],
            },

        'ALC271X': {
            'files'   : [ ],
            },

        'Cirrus Analog': {
            'files'   : [ ],
            },

        'ALC272': {
            'files'   : [ ],
            }
        }

    def exec_cmd(self, cmd):
        return utils.system(cmd, ignore_status = True)

    def pathname_must_exist(self, pathname):
        if not os.path.exists(pathname):
            logging.error("File missing: '%s'", pathname)
            return False
        return True

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
            if self.exec_cmd("aplay -Dhw:0 -l|grep -e '%s'" % (c)) == 0:
                return c
        raise error.TestError('Unable to determine sound codec.')

    def get_codec_basename(self, codec):
        return codec.replace(' ', '_')

    def get_data_pathname(self, filename):
        return os.path.join(self.bindir, filename)

    def validate_files(self, files_list):
        errors = 0
        for f in files_list:
            if not self.pathname_must_exist(f):
                errors += 1
        return errors

    def validate_codec(self, codec):
        err_str = ''
        errors = self.validate_files(codec['files'])
        if errors:
            err_str += " files: %d" % errors

        if err_str != '':
            err_str = "(%s)%s" % (self._codec_basename, err_str)
        return err_str

    def read_codec_data(self, codec):
        self._codec_basename = self.get_codec_basename(codec)

        # Read files which must be present.
        pathname = self.get_data_pathname(self._codec_basename + ".files")
        self.codec_info[codec]['files'] = [line.strip() for line in
                                           open(pathname)]

    def load_asound_state(self):
        if self.exec_cmd("alsactl --file /etc/asound.state restore 0") != 0:
            raise error.TestError("Unable to load /etc/asound.state")

    def run_once(self):
        codec = self.get_codec()
        self.read_codec_data(codec)
        err_str = ''
        if codec in self.codec_info:
            err_str += self.validate_codec(self.codec_info['ALL'])
            err_str += self.validate_codec(self.codec_info[codec])
            if err_str != '':
                raise error.TestError("codec validation failed.  %s" %
                                      (err_str))
        else:
            raise error.TestError("No test info for codec '%s'." % (codec))
