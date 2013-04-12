# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test to probe the video capability."""
import logging, os, sys
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

# The following VA_XXX values are copied from va/va.h
# VA profiles that we are interested in
VAProfileH264Baseline = 5
VAProfileH264Main = 6
VAProfileH264High = 7

# VA Entrypoint that we are interested in
VAEntrypointVLD = 1

# VA_RT_FORMAT that we are interested in
VA_RT_FORMAT_YUV420 = 0x01

class hardware_VideoDecodeCapable(test.test):
    """Test class to verify hardware video decoding capability."""

    version = 1

    REQUESTED_VAAPI_PROFILES = [
        VAProfileH264Baseline,
        VAProfileH264Main,
        VAProfileH264High]

    REQUESTED_V4L2_FORMATS = [
        'cap_fmt_VM12',
        'cap_fmt_NM12',
        'out_fmt_H264',
        'out_fmt_VP80']

    def assertTrue(self, condition, message = '', *args):
        """Raises an TestFail when the assertion failed"""
        if (not condition):
            raise error.TestFail(message % args)


    def verifyProfile(self, vaapi, display, profile):
        """Verifies the given profile satisfies the requirements.

        1. It has the VLD entrypoint
        2. It supports  YUV420 for RT_FORMAT

        @param vaapi: the vaapi module

        @param display: the va_display instance

        @param profile: the profile under test

        @raise error.TestFail: when verification fails
        """
        entrypoints = vaapi.query_entrypoints(display, profile)
        logging.info('Entrypoints of profile %s: %s', profile, entrypoints)
        self.assertTrue(VAEntrypointVLD in entrypoints,
                        'VAEntrypointVLD is not supported')

        rt_format = vaapi.get_rt_format(display, profile, VAEntrypointVLD)
        logging.info('RT_Format: %s', rt_format)
        self.assertTrue(VA_RT_FORMAT_YUV420 & rt_format,
                        'VA_RT_FORMAT_YUV420 is not supported');


    def setup(self):
        os.chdir(self.srcdir)

        # Ignores the fail status since vaapi module won't get built on
        # platforms without VAAPI support (e.g., Daisy). On those platforms
        # we will test with the v4l2 module.
        utils.make('v4l2', ignore_status = True)
        utils.make('vaapi', ignore_status = True)


    def run_once_vaapi(self):
        sys.path.append(self.bindir)
        import vaapi

        # Set the XAUTHORITY for connecting to the X server
        os.environ.setdefault('XAUTHORITY', '/home/chronos/.Xauthority')

        display = vaapi.create_display(':0.0')
        supported_profiles = vaapi.query_profiles(display);
        logging.info('Vaapi Profiles: %s', supported_profiles);

        for profile in self.REQUESTED_VAAPI_PROFILES:
            self.assertTrue(profile in supported_profiles,
                            'Profile:%s is not supported',
                            profile)
            self.verifyProfile(vaapi, display, profile)


    def _enum_formats(self, video_device):
        """Use the v4l2 binary to enum formats.

        Runs the embedded v4l2 binary to enumerate supported
        capture formats and output formats.

        @param video_device: device interrogated (e.g. /dev/mfc-dec).

        @return a dict of keyvals reflecting the formats supported.
        """
        sys.path.append(self.bindir)
        import v4l2

        capture_formats = v4l2.enum_capture_formats(video_device)
        logging.info('Capture formats=%s', capture_formats)
        output_formats = v4l2.enum_output_formats(video_device)
        logging.info('Output formats=%s', output_formats)

        return (['cap_fmt_%s' % fmt for fmt in capture_formats] +
                ['out_fmt_%s' % fmt for fmt in output_formats])


    def run_once_v4l2(self, video_device=None):
        """Emit supported image formats as keyvals.

        @param video_device: used by v4l2 binary to enum formats.
        """
        if not video_device:
            raise error.TestError('no video_device supplied to check')
        missed = (set(self.REQUESTED_V4L2_FORMATS) -
                  set(self._enum_formats(video_device)))
        self.assertTrue(not missed, 'Formats: %s is not supported', missed)


    def run_once(self, type='v4l2', **kwargs):
        if type == 'v4l2':
            video_device = kwargs['video_device']
            self.run_once_v4l2(video_device = video_device)
        else:
            self.run_once_vaapi()

