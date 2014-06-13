# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module exports the containers for extra descriptors.

HeaderFunctionalDescriptor - the class holds fields of a header functional
        descriptor.
UnionFunctionalDescriptor - the class holds fields of a union functional
        descriptor.
MBIMFunctionalDescriptor - the class holds fields of a MBIM functional
        descriptor.
MBIMExtendedFunctionalDescriptor - the class holds fields of a MBIM extended
        functional descriptor.
InterfaceAssociationDescriptor - the class holds fields of a interface
        association descriptor.
"""

class HeaderFunctionalDescriptor:
    """ Container for header functional descriptor. """
    def __init__(self,
                 bLength,
                 bDescriptorType,
                 bDescriptorSubtype,
                 bcdCDC):
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.bDescriptorSubtype = bDescriptorSubtype
        self.bcdCDC = bcdCDC


class UnionFunctionalDescriptor:
    """ Container for union functional descriptor. """
    def __init__(self,
                 bLength,
                 bDescriptorType,
                 bDescriptorSubtype,
                 bControlInterface,
                 bSubordinateInterface0):
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.bDescriptorSubtype = bDescriptorSubtype
        self.bControlInterface = bControlInterface
        self.bSubordinateInterface0 = bSubordinateInterface0


class MBIMFunctionalDescriptor:
    """ Container for MBIM functional descriptor. """
    def __init__(self,
                 bLength,
                 bDescriptorType,
                 bDescriptorSubtype,
                 bcdMBIMVersion,
                 wMaxControlMessage,
                 bNumberFilters,
                 bMaxFilterSize,
                 wMaxSegmentSize,
                 bmNetworkCapabilities):
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.bDescriptorSubtype = bDescriptorSubtype
        self.bcdMBIMVersion = bcdMBIMVersion
        self.wMaxControlMessage = wMaxControlMessage
        self.bNumberFilters = bNumberFilters
        self.bMaxFilterSize = bMaxFilterSize
        self.wMaxSegmentSize = wMaxSegmentSize
        self.bmNetworkCapabilities = bmNetworkCapabilities


class MBIMExtendedFunctionalDescriptor:
    """ Container for MBIM extended functional descriptor. """
    def __init__(self,
                 bLength,
                 bDescriptorType,
                 bDescriptorSubtype,
                 bcdMBIMEFDVersion,
                 bMaxOutstandingCommandMessages):
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.bDescriptorSubtype = bDescriptorSubtype
        self.bcdMBIMEFDVersion = bcdMBIMEFDVersion
        self.bMaxOutstandingCommandMessages = bMaxOutstandingCommandMessages


class InterfaceAssociationDescriptor:
    """ Container for interface association descriptor. """
    def __init__(self,
                 bLength,
                 bDescriptorType,
                 bFirstInterface,
                 bInterfaceCount,
                 bFunctionClass,
                 bFunctionSubClass,
                 bFunctionProtocol,
                 iFunction):
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.bFirstInterface = bFirstInterface
        self.bInterfaceCount = bInterfaceCount
        self.bFunctionClass = bFunctionClass
        self.bFunctionSubClass = bFunctionSubClass
        self.bFunctionProtocol = bFunctionProtocol
        self.iFunction = iFunction
