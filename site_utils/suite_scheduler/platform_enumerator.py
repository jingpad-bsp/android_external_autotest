# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import frontend_wrappers
from autotest_lib.server import frontend


class EnumeratorException(Exception):
    """Base class for exceptions from this module."""
    pass


class EnumerateException(EnumeratorException):
    """Raised when an error is returned from the AFE during enumeration."""
    pass


class NoPlatformException(EnumeratorException):
    """Raised when an error is returned from the AFE during enumeration."""


    def __init__(self):
        super(NoPlatformException, self).__init__('No supported platforms.')


class PlatformEnumerator(object):
    """Talks to the AFE and enumerates the platforms it knows about.

    @var _afe: a frontend.AFE instance used to talk to autotest.
    """

    _LABEL_PREFIX = 'board:'


    def __init__(self, afe=None):
        """Constructor

        @param afe: an instance of AFE as defined in server/frontend.py.
        """
        self._afe = afe


    def Enumerate(self):
        """Enumerate currently supported platforms.

        Lists all labels known to the AFE that start with self._LABEL_PREFIX,
        as this is the way that we define 'platforms' in the AFE today.

        @return list of platform names, e.g. 'x86-mario'
        """
        try:
            labels = self._afe.get_labels(name__startswith=self._LABEL_PREFIX)
        except Exception as e:
            raise EnumerateException(e)

        if not labels:
            raise NoPlatformException()

        return map(lambda l: l.name.split(':', 1)[1], labels)
