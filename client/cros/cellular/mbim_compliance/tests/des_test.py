# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import common
from autotest_lib.client.cros.cellular.mbim_compliance.tests import test


class DesTest(test.Test):
    """ Base class for descriptor tests. """

    # All the MBIM_ONLY_* maps are filters for MBIM only function. These maps
    # specify the values of the fields which should be matched in the target
    # interface.
    MBIM_ONLY_COMMUNICATION_INTERFACE = {'bAlternateSetting': 0,
                                         'bNumEndpoints': 1,
                                         'bInterfaceClass': 0x02,
                                         'bInterfaceSubClass': 0x0E,
                                         'bInterfaceProtocol': 0x00}

    MBIM_ONLY_DATA_INTERFACE_NO_DATA = {'bAlternateSetting': 0,
                                        'bNumEndpoints': 0,
                                        'bInterfaceClass': 0x0A,
                                        'bInterfaceSubClass': 0x00,
                                        'bInterfaceProtocol': 0x02}

    MBIM_ONLY_DATA_INTERFACE_MBIM = {'bAlternateSetting': 1,
                                     'bNumEndpoints': 2,
                                     'bInterfaceClass': 0x0A,
                                     'bInterfaceSubClass': 0x00,
                                     'bInterfaceProtocol': 0x02}

    # All the NCM_MBIM_* maps are filters for NCM/MBIM function. These maps
    # specify the values of the fields which should be matched in the target
    # interface.
    NCM_MBIM_COMMUNICATION_INTERFACE_NCM = {'bAlternateSetting': 0,
                                            'bNumEndpoints': 1,
                                            'bInterfaceClass': 0x02,
                                            'bInterfaceSubClass': 0x0D}

    NCM_MBIM_COMMUNICATION_INTERFACE_MBIM = {'bAlternateSetting': 0,
                                             'bNumEndpoints': 1,
                                             'bInterfaceClass': 0x02,
                                             'bInterfaceSubClass': 0x0E,
                                             'bInterfaceProtocol': 0x00}

    NCM_MBIM_DATA_INTERFACE_NO_DATA = {'bAlternateSetting': 0,
                                       'bNumEndpoints': 0,
                                       'bInterfaceClass': 0x0A,
                                       'bInterfaceSubClass': 0x00,
                                       'bInterfaceProtocol': 0x01}

    NCM_MBIM_DATA_INTERFACE_NCM = {'bAlternateSetting': 1,
                                   'bNumEndpoints': 2,
                                   'bInterfaceClass': 0x0A,
                                   'bInterfaceSubClass': 0x00,
                                   'bInterfaceProtocol': 0x01}

    NCM_MBIM_DATA_INTERFACE_MBIM = {'bAlternateSetting': 2,
                                    'bNumEndpoints': 2,
                                    'bInterfaceClass': 0x0A,
                                    'bInterfaceSubClass': 0x00,
                                    'bInterfaceProtocol': 0x02}


    def filter_interface_descriptors(self, descriptors, interface_type):
        """
        Filter interface descriptors based on the values in fields.

        @param descriptors: A list of interface descriptors.
        @param interface_type: A dictionary composed of pairs(field: value) to
                 match the target interface.
        @returns A list of target interfaces.

        """
        def match_all_fields(interface):
            """
            Match fields for a given interface descriptor based on the fields
            provided in |interface_type|.

            @param interface: An interface descriptor.
            @returns True if all fields match, False otherwise.

            """
            for key, value in interface_type.iteritems():
                if (not hasattr(interface, key) or
                    getattr(interface, key) != value):
                    return False
            return True

        return filter(lambda descriptor: match_all_fields(descriptor),
                      descriptors)


    def has_bulk_in_and_bulk_out(self, endpoints):
        """
        Check if there are one bulk-in endpoint and one bulk-out endpoint.

        @param endpoints: A list of endpoint descriptors.
        @returns True if there are one bulk-in and one bulk-out endpoint, False
                otherwise.
        """
        bulk_in, bulk_out = False, False
        for endpoint in endpoints:

            if (endpoint.bLength == 7 and
                endpoint.bEndpointAddress < 0x80 and
                endpoint.bmAttributes == 0x02):
                bulk_out = True
            elif (endpoint.bLength == 7 and
                  endpoint.bEndpointAddress >= 0x80 and
                  endpoint.bmAttributes == 0x02):
                bulk_in = True
        return bulk_in and bulk_out
