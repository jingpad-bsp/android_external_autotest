# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class XmlRpcStruct(object):
    """Superclass for structs passed to XmlRpcServer.

    Many methods we want to call remotely can be configured with many different
    parameters and return lots of data about what happened.  In the past, we
    felt free to pass parameters and results around as dictionaries.  However,
    this led us to a situation where it was difficult to tell what parameters
    were valid and expected.

    Take a simple step toward making these relationships explicit and recorded
    in one place by defining structs to bundle these variables explicitly.
    Unfortunately, XmlRpc doesn't know how to serialize Python objects working
    as structs, so we go back to dictionaries on the wire.

    Thus, a typical usage would look like:

    class AssociationParameters(XmlRpcStruct):
        ...

    params = AssociationParameters()
    params.ssid = 'MyHomeNetwork'
    params.psk = 'supersecret'
    params.security = 'wpa'
    raw_result = proxy.ConnectWiFiMethod(params.serialize())
    result = AssociationResult(raw_result)
    if (result.success):
        ....

    """

    def serialize(self):
        """Serialize a XmlRpcStruct for passing over the wire via XmlRpc.

        @return dict representing this struct.

        """
        return dict(vars(self).items())


    def __repr__(self):
        return '%s(%r)' % (self.__class__, self.__dict__)
