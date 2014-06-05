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

    MBIM_ASSERTIONS = {
            # This key should not be used directly.
            # Raise |MBIMComplianceGenericAssertionError| instead.
            'no_code': '',

            'mbim1.0:3.2.1#1': 'Functions that implement both NCM 1.0 and MBIM '
                               'shall provide two alternate settings for the '
                               'Communication Interface.',
            'mbim1.0:3.2.1#2': 'For alternate setting 0 of the Communication '
                               'Interface of an NCM/MBIM function: interface, '
                               'functional and endpoint descriptors shall be '
                               'constructed according to the rules given in '
                               '[USBNCM10].',
            'mbim1.0:3.2.1#2': 'For alternate setting 1 of the Communication '
                               'Interface of an NCM/MBIM function: interface, '
                               'functional and endpoint descriptors shall be '
                               'constructed according to the rules given in '
                               '[MBIM 1.0] section 6.',
            'mbim1.0:3.2.1#4': 'When alternate setting 0 of the Communiation'
                               'Interface of an NCM/MBIM function is selected, '
                               'the function shall operator according to the '
                               'NCM rules givein in [USBNCM10].',
            'mbim1.0:3.2.1#5': 'When alternate setting 1 of the Communiation'
                               'Interface of an NCM/MBIM function is selected, '
                               'the function shall operator according to the '
                               'MBIM rules given in [MBIM1.0].',
            'mbim1.0:3.2.2.1#1': 'If an Interface Association Descriptor is '
                                 'used to form an NCM/MBIM function, its '
                                 'interface class, subclass, and protocol '
                                 'codes shall match those given in alternate '
                                 'setting 0 of the Communication Interface. ',
            # TODO(mcchou): Add other assertions as needed.
    }

    def __init__(self, assertion_id, error_string=None):
        """
        @param assertion_id: A str that must be a key in the MBIM_ASSERTIONS map
                defined in this class.
        @param error_string: An optional str to be appended to the error
                description.

        For example,
            MBIMComplianceAssertionError('mbim1.0:3.2.1#1')
            raises an error associated with assertion [MBIM 1.0]-3.2.1#1

        """
        if assertion_id not in self.MBIM_ASSERTIONS:
            log_and_raise(MBIMComplianceFrameworkError,
                          'Unknown assertion id "%s"' % assertion_id)

        message = '[%s]: %s' % (assertion_id,
                                self.MBIM_ASSERTIONS[assertion_id])
        if error_string:
            message += ': %s' % error_string

        super(MBIMComplianceAssertionError, self).__init__(message)


class MBIMComplianceGenericAssertionError(MBIMComplianceAssertionError):
    """ Assertion errors that don't map directly to an MBIM assertion. """
    def __init__(self, error_string):
        """
        @param error_string: A description of the error.
        """
        super(MBIMComplianceGenericAssertionError, self).__init__(
                'no_code',
                error_string)


def log_and_raise(error_class, *args):
    """
    Log and raise an error.

    This function should be used to raise all errors.

    @param error_class: An Exception subclass to raise.
    @param *args: Arguments to be passed to the error class constructor.
    @raises: |error_class|.

    """
    error_object = error_class(*args)
    logging.error(error_object)
    trace = traceback.format_stack()
    # Get rid of the current frame from trace
    trace = trace[:len(trace)-1]
    logging.error('Traceback:\n' + ''.join(trace))
    raise error_object
