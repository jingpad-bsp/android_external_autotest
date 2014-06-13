# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Utility functions

This module contains useful utility functions for MBIM Compliance Test Suite.

"""

import logging

import common
from autotest_lib.client.cros.cellular.mbim_compliance import containers
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


def get_interface_extra_descriptors(extra_bytes):
    """
    Parse extra descriptors of an interface.

    @returns a list of functional descriptors

    """
    extra_descriptors = []
    extra_len = len(extra_bytes)
    descriptor_start_index = 0
    # Iterate byte stream
    while descriptor_start_index < extra_len:
        # Extract distinct blocks from byte stream
        descriptor_length = extra_bytes[descriptor_start_index]
        stream = (extra_bytes[descriptor_start_index:descriptor_start_index +
                              descriptor_length])
        descriptor_start_index += extra_bytes[descriptor_start_index]
        descriptor_type = stream[1]
        descriptor_subtype = stream[2]
        # Avoid parsing descriptors of other interface
        # 0x05 refers to endpoint descriptor type
        # 0x24 refers to functional descriptor type
        # 0x25 refers to audio data functional descriptor type
        # 0x30 refers to endpoint companion descriptor type
        if not(descriptor_type == 0x24 or descriptor_type == 0x25 or
               descriptor_type == 0x05 or descriptor_type == 0x30):
            break
        # Parse header functional descriptor
        if descriptor_subtype == 0x00:
            header_functional_descriptor = (
                    containers.HeaderFunctionalDescriptor(
                            stream[0],
                            stream[1],
                            stream[2],
                            stream[3] | (stream[4]<<8)))
            extra_descriptors.append(header_functional_descriptor)
        # Parse union function descriptor
        elif descriptor_subtype == 0x06:
            union_functional_descriptor = containers.UnionFunctionalDescriptor(
                    stream[0],
                    stream[1],
                    stream[2],
                    stream[3],
                    stream[4])
            extra_descriptors.append(union_functional_descriptor)
        # Parse MBIM functional descriptor
        elif descriptor_subtype == 0x1B:
            MBIM_functional_descriptor = containers.MBIMFunctionalDescriptor(
                    stream[0],
                    stream[1],
                    stream[2],
                    stream[3] | (stream[4] << 8),
                    stream[5] | (stream[6] << 8),
                    stream[7],
                    stream[8],
                    stream[9] | (stream[10] << 8),
                    stream[11])
            extra_descriptors.append(MBIM_functional_descriptor)
        # Parse MBIM extended functional descriptor
        elif descriptor_subtype == 0x1C:
            MBIM_extended_functional_descriptor = (
                    containers.MBIMExtendedFunctionalDescriptor(
                    stream[0],
                    stream[1],
                    stream[2],
                    stream[3] | (stream[4] << 8),
                    stream[5]))
            extra_descriptors.append(MBIM_extended_functional_descriptor)
        # Exception for unknown bDescriptorSubtype
        else:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceGenericAssertionError,
                    'Parser: unknown bDescriptorSubtype')
    return extra_descriptors


def get_configuration_extra_descriptors(extra_bytes):
    """
    Parse extra descriptors of a configuration.

    @returns a list of interface association descriptor

    """
    interface_association_descriptors = []
    extra_len = len(extra_bytes)
    index = 0
    while index < extra_len:
        stream = extra_bytes[index: index + extra_bytes[index]]
        index += extra_bytes[index]
        descriptor_type = stream[1]
        if descriptor_type == 0x0B:
            interface_association_descriptor = (
                    containers.InterfaceAssociationDescriptor(stream[0],
                                                              stream[1],
                                                              stream[2],
                                                              stream[3],
                                                              stream[4],
                                                              stream[5],
                                                              stream[6],
                                                              stream[7]))
            interface_association_descriptors.append(
                    interface_association_descriptor)
        else:
            mbim_errors.log_raise(mbim_errors.MBIMComplianceFrameworkError,
                                  'Parser: wrong bDescriptorType for interface'
                                  'association descriptor')
    return interface_association_descriptors


def descriptor_filter(descriptor_type, descriptors):
    """
    Filter a list of descriptors based on target descriptor type.

    @param descriptor_type: target descriptor type
    @param descriptors: the list of functional descriptors
    @returns a set of tuples(index, descriptor)

    """
    return filter(lambda (index, descriptor): isinstance(descriptor,
                                                         descriptor_type),
                  enumerate(descriptors))


def has_distinct_descriptors(descriptor_tuples):
    """
    Check if there are distinct descriptors of the target descriptor type.

    @param descriptor_tuples: the list of descriptor tuples(index, descriptor)
    @returns True if distinct descriptor are found, False otherwise.

    """
    return not all([descriptor == descriptor_tuples[0][1]
                    for (_, descriptor) in descriptor_tuples])


def print_extra_bytes(configuration_extra=None, interface_extra=None):
    """
    Print extra bytes for a configuration or an interface

    @param configuration_extra: extra bytes of configuration descriptor
    @param interface_extra: extra bytes of interface descriptor

    """
    if configuration_extra is not None:
        configuration_extra_len = len(configuration_extra)
        logging.debug('Length of configuration extra bytes: %d',
                configuration_extra_len)
        index = 0
        while(index < configuration_extra_len):
            l = configuration_extra[index]
            logging.debug(' '.join(
                    ['%02X' % b for b in configuration_extra[index:index + l]]))
            index += l
    if interface_extra is not None:
        interface_extra_len = len(interface_extra)
        logging.debug('Length of interface extra bytes: %d',
                interface_extra_len)
        index = 0
        while(index < interface_extra_len):
            l = interface_extra[index]
            logging.debug(' '.join(
                    ['%02X' % b for b in interface_extra[index:index + l]]))
            index += l


def print_device_descriptor(device):
    """
    Print device descriptor.

    @param device: device object

    """
    logging.debug(device)
    bConfigurationValue = device.get_active_configuration().bConfigurationValue
    logging.debug('idVender: %s', hex(device.idVendor))
    logging.debug('idProduct: %s', hex(device.idProduct))
    logging.debug('bConfigurationValue: %d', bConfigurationValue)
    logging.debug('bNumConfigurations: %d', device.bNumConfigurations)


def print_interface_descriptor(interface):
    """
    Print interface descriptor.

    @param interface: interface object

    """
    print interface
    logging.debug('bInterfaceNumber: %d', interface.bInterfaceNumber)
    logging.debug('bDescriptorType: %02X', interface.bDescriptorType)
    logging.debug('bAlternateSetting: %d', interface.bAlternateSetting)
    logging.debug('bNumEndpoints: %d', interface.bNumEndpoints)
    logging.debug('bInterfaceClass: %02X', interface.bInterfaceClass)
    logging.debug('bInterfaceSubClass: %02X', interface.bInterfaceSubClass)
    logging.debug('bInterfaceProtocol: %02X', interface.bInterfaceProtocol)
