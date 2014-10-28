# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to access the local audio facade."""

from autotest_lib.client.cros.multimedia import audio_facade_native


class AudioFacadeLocalAdapter(audio_facade_native.AudioFacadeNative):
    """AudioFacadeLocalAdapter is an adapter to control the local audio.

    Methods with non-native-type arguments go to this class and do some
    conversion; otherwise, go to the AudioFacadeNative class.
    """
    # TODO: Add methods to adapt the native ones once any non-native-type
    # methods are added.
    pass
