# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import traceback

import common
from autotest_lib.client.common_lib import error


class MBIMComplianceError(error.TestFail):
    """ Base class for all errors overtly raised in the suite. """
    pass


class MBIMComplianceFrameworkError(MBIMComplianceError):
    """
    Errors raised by any of the framework code.

    These errors are raised by code that is not part of a test / sequence /
    assertion.

    """
    pass


class MBIMComplianceTestError(MBIMComplianceError):
    """ Errors raised by compliance suite tests. """
    pass


class MBIMComplianceSequenceError(MBIMComplianceError):
    """ Errors raised by compliance suite sequences. """
    pass


class MBIMComplianceAssertionError(MBIMComplianceError):
    """ Errors raised by compliance suite assertions. """
    pass


def log_and_raise(error_class, error_string=None):
    """
    Log and raise an error.

    This function should be used to raise all errors.

    @param error_class: An Exception subclass to raise.
    @param error_string: A string describing the error condition.
    @raises: |error_class|.

    """
    error_string = error_string if error_string is not None else ''
    error_object = error_class(error_string)
    logging.error(error_object)
    trace = traceback.format_stack()
    # Get rid of the current frame from trace
    trace = trace[:len(trace)-1]
    logging.error('Traceback:\n' + ''.join(trace))
    raise error_object
