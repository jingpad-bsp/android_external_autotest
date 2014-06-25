# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import struct
from collections import namedtuple

from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class DescriptorMeta(type):
    """
    Metaclass for creating a USB descriptor class.

    A derived descriptor class takes raw descriptor data as an array of unsigned
    bytes via its constructor and parses the data into individual fields stored
    as instance attributes. A derived class of |Descriptor| should specify the
    following class attributes as part of the class definition:

        DESCRIPTOR_TYPE: An unsigned 8-bit number specifying the descriptor
        type. Except for |UnknownDescriptor|, all derived classes should specify
        this attribute. This attribute can be inherited from a parent class.

        DESCRIPTOR_SUBTYPE: An unsigned 8-bit number specifying the descriptor
        subtype. Only descriptors have a bDescriptorSubtype field should specify
        this attribute.

        _FIELDS: A list of field definitions specified as a nested tuple. The
        field definitions are ordered in the same way as the fields are present
        in the USB descriptor. Each inner tuple is a field definition and
        contains two elements. The first element specifies the format
        character(s), which instructs |struct.unpack_from| how to extract the
        field from the raw descriptor data. The second element specifies the
        field name, which is also the attribute name used by an instance of the
        derived descriptor class for storing the field. Each derived descriptor
        class must define its own _FIELDS attribute, which must have
        ('B', 'bLength'), ('B', 'bDescriptorType') as the first two entries.

    """
    descriptor_classes = []

    def __new__(mcs, name, bases, attrs):
        # The Descriptor base class, which inherits from 'object', is merely
        # used to establish the class hierarchy and is never constructed from
        # raw descriptor data.
        if object in bases:
            return super(DescriptorMeta, mcs).__new__(mcs, name, bases, attrs)

        if '_FIELDS' not in attrs:
            raise mbim_errors.MBIMComplianceFrameworkError(
                    '%s must define a _FIELDS attribute' % name)

        field_formats, field_names = zip(*attrs['_FIELDS'])
        # USB descriptor data are in the little-endian format.
        data_format = '<' + ''.join(field_formats)
        unpack_length = struct.calcsize(data_format)

        def descriptor_class_new(cls, data):
            """
            Creates a descriptor instance with the given descriptor data.

            @param cls: The descriptor class of the instance to be created.
            @param data: The raw descriptor data as an array of unsigned bytes.
            @returns The descriptor instance.

            """
            data_length = len(data)

            if unpack_length > data_length:
                raise mbim_errors.MBIMComplianceFrameworkError(
                        'Expected %d or more bytes of descriptor data, got %d' %
                        (unpack_length, data_length))

            obj = super(cls, cls).__new__(cls, *struct.unpack_from(data_format,
                                                                   data))
            setattr(obj, 'data', data)

            descriptor_type = attrs.get('DESCRIPTOR_TYPE')
            if (descriptor_type is not None and
                descriptor_type != obj.bDescriptorType):
                raise mbim_errors.MBIMComplianceFrameworkError(
                        'Expected descriptor type 0x%02X, got 0x%02X' %
                        (descriptor_type, obj.bDescriptorType))

            descriptor_subtype = attrs.get('DESCRIPTOR_SUBTYPE')
            if (descriptor_subtype is not None and
                descriptor_subtype != obj.bDescriptorSubtype):
                raise mbim_errors.MBIMComplianceFrameworkError(
                        'Expected descriptor subtype 0x%02X, got 0x%02X' %
                        (descriptor_subtype, obj.bDescriptorSubtype))

            if data_length != obj.bLength:
                raise mbim_errors.MBIMComplianceFrameworkError(
                        'Expected descriptor length %d, got %d' %
                        (data_length, obj.bLength))

            # TODO(benchan): We don't currently handle the case where
            # |data_length| > |unpack_length|, which happens if the descriptor
            # contains a variable length field (e.g. StringDescriptor).

            return obj

        attrs['__new__'] = descriptor_class_new
        descriptor_class = namedtuple(name, field_names)
        # Prepend the class created via namedtuple to |bases| in order to
        # correctly resolve the __new__ method while preserving the class
        # hierarchy.
        cls = super(DescriptorMeta, mcs).__new__(mcs, name,
                                                 (descriptor_class,) + bases,
                                                 attrs)
        # As Descriptor.__subclasses__() only reports its direct subclasses,
        # we keep track of all subclasses of Descriptor using the
        # |DescriptorMeta.descriptor_classes| attribute.
        mcs.descriptor_classes.append(cls)
        return cls


class Descriptor(object):
    """
    USB Descriptor base class.

    This class should not be instantiated or used directly.

    """
    __metaclass__ = DescriptorMeta


class UnknownDescriptor(Descriptor):
    """
    Unknown USB Descriptor.

    This class is a catch-all descriptor for unsupported or unknown descriptor
    types.
    """
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'))


class DeviceDescriptor(Descriptor):
    """ Device Descriptor. """
    DESCRIPTOR_TYPE = 0x01
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('H', 'bcdUSB'),
               ('B', 'bDeviceClass'),
               ('B', 'bDeviceSubClass'),
               ('B', 'bDeviceProtocol'),
               ('B', 'bMaxPacketSize0'),
               ('H', 'idVendor'),
               ('H', 'idProduct'),
               ('H', 'bcdDevice'),
               ('B', 'iManufacturer'),
               ('B', 'iProduct'),
               ('B', 'iSerialNumber'),
               ('B', 'bNumConfigurations'))


class ConfigurationDescriptor(Descriptor):
    """ Configuration Descriptor. """
    DESCRIPTOR_TYPE = 0x02
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('H', 'wTotalLength'),
               ('B', 'bNumInterfaces'),
               ('B', 'bConfigurationValue'),
               ('B', 'iConfiguration'),
               ('B', 'bmAttributes'),
               ('B', 'bMaxPower'))


class InterfaceDescriptor(Descriptor):
    """ Interface Descriptor. """
    DESCRIPTOR_TYPE = 0x04
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bInterfaceNumber'),
               ('B', 'bAlternateSetting'),
               ('B', 'bNumEndpoints'),
               ('B', 'bInterfaceClass'),
               ('B', 'bInterfaceSubClass'),
               ('B', 'bInterfaceProtocol'),
               ('B', 'iInterface'))


class EndpointDescriptor(Descriptor):
    """ Endpoint Descriptor. """
    DESCRIPTOR_TYPE = 0x05
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bEndpointAddress'),
               ('B', 'bmAttributes'),
               ('H', 'wMaxPacketSize'),
               ('B', 'bInterval'))


class InterfaceAssociationDescriptor(Descriptor):
    """ Interface Asscociation Descriptor. """
    DESCRIPTOR_TYPE = 0x0B
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bFirstInterface'),
               ('B', 'bInterfaceCount'),
               ('B', 'bFunctionClass'),
               ('B', 'bFunctionSubClass'),
               ('B', 'bFunctionProtocol'),
               ('B', 'iFunction'))


class FunctionalDescriptor(Descriptor):
    """ Functional Descriptor. """
    DESCRIPTOR_TYPE = 0x24
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bDescriptorSubtype'))


class HeaderFunctionalDescriptor(FunctionalDescriptor):
    """ Header Functional Descriptor. """
    DESCRIPTOR_SUBTYPE = 0x00
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bDescriptorSubtype'),
               ('H', 'bcdCDC'))


class UnionFunctionalDescriptor(FunctionalDescriptor):
    """ Union Functional Descriptor. """
    DESCRIPTOR_SUBTYPE = 0x06
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bDescriptorSubtype'),
               ('B', 'bControlInterface'),
               ('B', 'bSubordinateInterface0'))


class MBIMFunctionalDescriptor(FunctionalDescriptor):
    """ MBIM Functional Descriptor. """
    DESCRIPTOR_SUBTYPE = 0x1B
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bDescriptorSubtype'),
               ('H', 'bcdMBIMVersion'),
               ('H', 'wMaxControlMessage'),
               ('B', 'bNumberFilters'),
               ('B', 'bMaxFilterSize'),
               ('H', 'wMaxSegmentSize'),
               ('B', 'bmNetworkCapabilities'))


class MBIMExtendedFunctionalDescriptor(FunctionalDescriptor):
    """ MBIM Extended Functional Descriptor. """
    DESCRIPTOR_SUBTYPE = 0x1C
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bDescriptorSubtype'),
               ('H', 'bcdMBIMExtendedVersion'),
               ('B', 'bMaxOutstandingCommandMessages'),
               ('H', 'wMTU'))


class SuperSpeedEndpointCompanionDescriptor(Descriptor):
    """ SuperSpeed Endpoint Companion Descriptor. """
    DESCRIPTOR_TYPE = 0x30
    _FIELDS = (('B', 'bLength'),
               ('B', 'bDescriptorType'),
               ('B', 'bMaxBurst'),
               ('B', 'bmAttributes'),
               ('H', 'wBytesPerInterval'))


class DescriptorParser(object):
    """
    A class for extracting USB descriptors from raw descriptor data.

    This class takes raw descriptor data as an array of unsigned bytes via its
    constructor and provides an iterator interface to return individual USB
    descriptors via instances derived from a subclass of Descriptor.

    """
    _DESCRIPTOR_CLASS_MAP = {
            (cls.DESCRIPTOR_TYPE, getattr(cls, 'DESCRIPTOR_SUBTYPE', None)): cls
            for cls in DescriptorMeta.descriptor_classes
            if hasattr(cls, 'DESCRIPTOR_TYPE')
    }

    def __init__(self, data):
        self._data = data
        self._data_length = len(data)
        self._index = 0
        # The position of each descriptor in the list.
        self._descriptor_index = 0

    def __iter__(self):
        return self

    def next(self):
        """
        Returns the next descriptor found in the descriptor data.

        @returns An instance of a subclass of Descriptor.
        @raises StopIteration if no more descriptor is found,

        """
        if self._index >= self._data_length:
            raise StopIteration

        # Identify the descriptor class based on bDescriptorType, and if
        # available, bDescriptorSubtype. The descriptor data has a standard
        # layout as follows:
        #   self._data[self._index]: bLength
        #   self._data[self._index + 1]: bDescriptorType
        #   self._data[self._index + 2]: bDescriptorSubtype for some descriptors
        descriptor_type, descriptor_subtype = None, None
        if self._index + 1 < self._data_length:
            descriptor_type = self._data[self._index + 1]
            if self._index + 2 < self._data_length:
                descriptor_subtype = self._data[self._index + 2]

        descriptor_class = self._DESCRIPTOR_CLASS_MAP.get(
                (descriptor_type, descriptor_subtype), None)
        if descriptor_class is None:
            descriptor_class = self._DESCRIPTOR_CLASS_MAP.get(
                    (descriptor_type, None), UnknownDescriptor)

        next_index = self._index + self._data[self._index]
        descriptor = descriptor_class(self._data[self._index:next_index])
        self._index = next_index
        descriptor.index = self._descriptor_index
        self._descriptor_index += 1
        return descriptor


def filter_descriptors(descriptor_type, descriptors):
    """
    Filter a list of descriptors based on the target |descriptor_type|.

    @param descriptor_type: The target descriptor type.
    @param descriptors: The list of functional descriptors.
    @returns A list of target descriptors.

    """
    if not descriptors:
        return []
    return filter(lambda descriptor: isinstance(descriptor, descriptor_type),
                  descriptors)


def has_distinct_descriptors(descriptors):
    """
    Check if there are distinct descriptors in the given list.

    @param descriptors: The list of descriptors.
    @returns True if distinct descriptor are found, False otherwise.

    """
    return not all(descriptor == descriptors[0] for descriptor in descriptors)
