# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.client.common_lib import error


def get_audio_client(fb_client_name):
    """Instantiates an audio feedback client.

    @param fb_client_name: Name of the desired client.

    @return An instance of client.common_lib.feedback.client.Client.
    """
    if not fb_client_name:
        raise error.TestError('Feedback client name is empty')
    if fb_client_name == 'loop':
        from autotest_lib.server.brillo.feedback import closed_loop_audio_client
        return closed_loop_audio_client.Client()
    else:
        raise error.TestError('Unknown feedback client (%s)' % fb_client_name)
