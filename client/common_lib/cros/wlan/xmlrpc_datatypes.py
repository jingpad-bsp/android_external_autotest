# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class WiFiXmlRpcStruct(object):
    """Superclass for structs passed to ShillXmlRpcServer.

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
        """Serialize a WiFiXmlRpcStruct for passing over the wire via XmlRpc.

        @return dict representing this struct.

        """
        return dict(vars(self).items())


    def __repr__(self):
        return '%s(%r)' % (self.__class__, self.__dict__)


class AssociationParameters(WiFiXmlRpcStruct):
    """Describes parameters used in WiFi connection attempts."""

    DEFAULT_SECURITY = 'none'
    DEFAULT_PSK = ''
    DEFAULT_DISCOVERY_TIMEOUT = 15
    DEFAULT_ASSOCIATION_TIMEOUT = 15
    DEFAULT_CONFIGURATION_TIMEOUT = 15

    def __init__(self, serialized=None):
        """Construct an AssociationParameters.

        @param serialized dict passed over the wire from XMLRPC server.

        """
        super(AssociationParameters, self).__init__()
        if serialized is None:
            serialized = {}
        # The network to connect to (e.g. 'GoogleGuest').
        self.ssid = serialized.get('ssid', None)
        # Which encryption to use (e.g. 'wpa').
        self.security = serialized.get('security', self.DEFAULT_SECURITY)
        # Passphrase for this network (e.g. 'password123').
        self.psk = serialized.get('psk', self.DEFAULT_PSK)
        # Max delta in seconds between XMLRPC call to connect in the proxy
        # and when shill finds the service.  Presumably callers call connect
        # quickly after configuring the AP so that this is an approximation
        # of how long takes shill to scan and discover new services.
        self.discovery_timeout = serialized.get('discovery_timeout',
                                                self.DEFAULT_DISCOVERY_TIMEOUT)
        # Max delta in seconds between service creation and the transition to
        # an associated state.
        self.association_timeout = serialized.get(
                'association_timeout',
                self.DEFAULT_ASSOCIATION_TIMEOUT)
        # Max delta in seconds between service association success and the
        # transition to online.
        self.configuration_timeout = serialized.get(
                'configuration_timeout',
                self.DEFAULT_CONFIGURATION_TIMEOUT)
        # True iff this is a hidden network.
        self.is_hidden = serialized.get('is_hidden', False)
        # Passing false tells shill not to remember the configured service.
        self.save_credentials = serialized.get('save_credentials', False)


class AssociationResult(WiFiXmlRpcStruct):
    """Describes the result of an association attempt."""

    def __init__(self, serialized=None):
        """Construct an AssociationResult.

        @param serialized dict passed over the wire from XMLRPC server.

        """
        super(AssociationResult, self).__init__()
        if serialized is None:
            serialized = {}
        # True iff we were successful in connecting to this WiFi network.
        self.success = serialized.get('success', False)
        # Describes how long it took to find and call connect on a network
        # From the time we proxy is told to connect.  This includes scanning
        # time.
        self.discovery_time = serialized.get('discovery_time', -1.0)
        # Describes how long it takes from the moment that we call connect to
        # the moment we're fully associated with the BSS.  This includes wpa
        # handshakes.
        self.association_time = serialized.get('association_time', -1.0)
        # Describes how long it takes from association till we have an IP
        # address and mark the network as being either online or portalled.
        self.configuration_time = serialized.get('configuration_time', -1.0)
        # Holds a descriptive reason for why the negotiation failed when
        # |successs| is False.  Undefined otherwise.
        self.failure_reason = serialized.get('failure_reason', 'unknown')


    @staticmethod
    def from_dbus_proxy_output(raw):
        """Factory for AssociationResult.

        The object which knows how to talk over DBus to shill is not part of
        autotest and as a result can't return a AssociationResult.  Instead,
        it returns a similar looing tuple, which we'll parse.

        @param raw tuple from ShillProxy.
        @return AssociationResult parsed output from ShillProxy.

        """
        result = AssociationResult()
        result.success = raw[0]
        result.discovery_time = raw[1]
        result.association_time = raw[2]
        result.configuration_time = raw[3]
        result.failure_reason = raw[4]
        return result
