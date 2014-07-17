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


class MBIMComplianceChannelError(MBIMComplianceError):
    """ Errors raised in the MBIM communication channel. """
    pass


class MBIMComplianceControlMessageError(MBIMComplianceError):
    """ Errors raised in the MBIM control module. """
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

            # Assertion group: 3.x.x#x
            'mbim1.0:3.2.1#1': 'Functions that implement both NCM 1.0 and MBIM '
                               'shall provide two alternate settings for the '
                               'Communication Interface.',
            'mbim1.0:3.2.1#2': 'For alternate setting 0 of the Communication '
                               'Interface of an NCM/MBIM function: interface, '
                               'functional and endpoint descriptors shall be '
                               'constructed according to the rules given in '
                               '[USBNCM10].',
            'mbim1.0:3.2.1#3': 'For alternate setting 1 of the Communication '
                               'Interface of an NCM/MBIM function: interface, '
                               'functional and endpoint descriptors shall be '
                               'constructed according to the rules given in '
                               '[MBIM 1.0] section 6.',
            'mbim1.0:3.2.1#4': 'When alternate setting 0 of the Communiation'
                               'Interface of an NCM/MBIM function is selected, '
                               'the function shall operator according to the '
                               'NCM rules given in [USBNCM10].',
            'mbim1.0:3.2.1#5': 'When alternate setting 1 of the Communiation'
                               'Interface of an NCM/MBIM function is selected, '
                               'the function shall operator according to the '
                               'MBIM rules given in [MBIM1.0].',
            'mbim1.0:3.2.2.1#1': 'If an Interface Association Descriptor is '
                                 'used to form an NCM/MBIM function, its '
                                 'interface class, subclass, and protocol '
                                 'codes shall match those given in alternate '
                                 'setting 0 of the Communication Interface. ',
            'mbim1.0:3.2.2.4#1': 'Functions that implement both NCM 1.0 and '
                                 'MBIM (an "NCM/MBIM function") shall provide '
                                 'three alternate settings for the Data '
                                 'Interface.',
            'mbim1.0:3.2.2.4#2': 'For an NCM/MBIM function, the Data Interface '
                                 'descriptors for alternate settings 0 and 1 '
                                 'must have bInterfaceSubClass == 00h, and '
                                 'bInterfaceProtocol == 01h.',
            'mbim1.0:3.2.2.4#3': 'For an NCM/MBIM function, the Data Interface '
                                 'descriptor for alternate setting 2 must have '
                                 'bInterfaceSubClass == 00h, and '
                                 'bInterfaceProtocol == 02h.',
            'mbim1.0:3.2.2.4#4': 'For an NCM/MBIM function there must be no '
                                 'endpoints for alternate setting 0 of the '
                                 'Data Interface. For each of the other two '
                                 'alternate settings (1 and 2) there must be '
                                 'exactly two endpoints: one Bulk IN and one '
                                 'Bulk OUT.',

            # Assertion group: 6.x#x
            'mbim1.0:6.1#1': 'If an Interface Association Descriptor (IAD) is '
                             'provided for the MBIM function, the IAD and the '
                             'mandatory CDC Union Functional Descriptor '
                             'specified for the MBIM function shall group '
                             'together the same interfaces.',
            'mbim1.0:6.1#2': 'If an Interface Association Descriptor (IAD) is '
                             'provided for the MBIM only function, its '
                             'interface class, subclass, and protocol codes '
                             'shall match those given in the Communication '
                             'Interface descriptor.',
            'mbim1.0:6.3#1': 'The descriptor for alternate setting 0 of the '
                             'Communication Interface of an MBIM only function '
                             'shall have bInterfaceClass == 02h, '
                             'bInterfaceSubClass == 0Eh, and '
                             'bInterfaceProtocol == 00h.',
            'mbim1.0:6.3#2': 'MBIM Communication Interface description shall '
                             'include the following functional descriptors: '
                             'CDC Header Functional Descriptor, CDC Union '
                             'Functional Descriptor, and MBIM Functional '
                             'Descriptor. Refer to Table 6.2 of [USBMBIM10].',
            'mbim1.0:6.3#3': 'CDC Header Functional Descriptor shall appear '
                             'before CDC Union Functional Descriptor and '
                             'before MBIM Functional Descriptor.',
            'mbim1.0:6.3#4': 'CDC Union Functional Descriptor for an MBIM '
                             'function shall group together the MBIM '
                             'Communication Interface and the MBIM Data '
                             'Interface.',
            'mbim1.0:6.3#5': 'The class-specific descriptors must be followed '
                             'by an Interrupt IN endpoint descriptor.',
            'mbim1.0:6.4#1': 'Field wMaxControlMessage of MBIM Functional '
                             'Descriptor must not be smaller than 64.',
            'mbim1.0:6.4#2': 'Field bNumberFilters of MBIM Functional '
                             'Descriptor must not be smaller than 16.',
            'mbim1.0:6.4#3': 'Field bMaxFilterSize of MBIM Functional '
                             'Descriptor must not exceed 192.',
            'mbim1.0:6.4#4': 'Field wMaxSegmentSize of MBIM Functional '
                             'Descriptor must not be smaller than 2048.',
            'mbim1.0:6.4#5': 'Field bFunctionLength of MBIM Functional '
                             'Descriptor must be 12 representing the size of '
                             'the descriptor.',
            'mbim1.0:6.4#6': 'Field bcdMBIMVersion of MBIM Functional '
                             'Descriptor must be 0x0100 in little endian '
                             'format.',
            'mbim1.0:6.4#7': 'Field bmNetworkCapabilities of MBIM Functional '
                             'Descriptor should have the following bits set to '
                             'zero: D0, D1, D2, D4, D6 and D7.',
            'mbim1.0:6.5#1': 'If MBIM Extended Functional Descriptor is '
                             'provided, it must appear after MBIM Functional '
                             'Descriptor.',
            'mbim1.0:6.5#2': 'Field bFunctionLength of MBIM Extended '
                             'Functional Descriptor must be 8 representing the '
                             'size of the descriptor.',
            'mbim1.0:6.5#3': 'Field bcdMBIMEFDVersion of MBIM Extended '
                             'Functional Descriptor must be 0x0100 in little '
                             'endian format.',
            'mbim1.0:6.5#4': 'Field bMaxOutstandingCommandMessages of MBIM '
                             'Extended Functional Descriptor shall be greater '
                             'than 0.',
            'mbim1.0:6.6#1': 'The Data Interface for an MBIM only function '
                             'shall provide two alternate settings.',
            'mbim1.0:6.6#2': 'The first alternate setting for the Data '
                             'Interface of an MBIM only function (the default '
                             'interface setting, alternate setting 0) shall '
                             'include no endpoints.',
            'mbim1.0:6.6#3': 'The second alternate setting for the Data '
                             'Interface of an MBIM only function (alternate '
                             'setting 1) is used for normal operation, and '
                             'shall include one Bulk IN endpoint and one Bulk '
                             'OUT endpoint.',
            'mbim1.0:6.6#4': 'For an MBIM only function the Data Interface '
                             'descriptors for alternate settings 0 and 1 must '
                             'have bInterfaceSubClass == 00h, and '
                             'bInterfaceProtocol == 02h. Refer to Table 6.4 of '
                             '[USBMBIM10].'
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
