# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_security_types


class AssociationParameters(object):
    """Describes parameters used in WiFi connection attempts."""

    DEFAULT_DISCOVERY_TIMEOUT = 15
    DEFAULT_ASSOCIATION_TIMEOUT = 15
    DEFAULT_CONFIGURATION_TIMEOUT = 15
    # Mode for most routers and access points.
    STATION_TYPE_MANAGED = 'managed'
    # Mode for certain kinds of p2p networks like old Android phone hotspots.
    STATION_TYPE_IBSS = 'ibss'

    @property
    def security(self):
        """@return string security type for this network."""
        return self.security_config.security


    @property
    def security_parameters(self):
        """@return dict of service property/value pairs related to security."""
        return self.security_config.get_shill_service_properties()


    def __init__(self, serialized=None):
        """Construct an AssociationParameters.

        @param serialized dict passed over the wire from XMLRPC server.

        """
        super(AssociationParameters, self).__init__()
        if serialized is None:
            serialized = {}
        # The network to connect to (e.g. 'GoogleGuest').
        self.ssid = serialized.get('ssid', None)
        # Marshall our bundle of security configuration.
        serialized_security_config = serialized.get('security_config', {})
        self.security_config = (
                xmlrpc_security_types.deserialize(serialized_security_config) or
                xmlrpc_security_types.SecurityConfig())
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
        # Station type to connect with.  Usually left unfilled unless we're
        # connecting to a non-managed BSS.
        self.station_type = serialized.get('station_type', None)


class AssociationResult(object):
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


class BgscanConfiguration(object):
    """Describes how to configure wpa_supplicant on a DUT."""

    RESET_VALUE = 'default'

    def __init__(self, serialized=None):
        """Construct a BgscanConfiguration.

        @param serialized dict passed over the wire from the autotest server.

        """
        super(BgscanConfiguration, self).__init__()
        if serialized is None:
            serialized = {}
        self.interface = serialized.get('interface', None)
        self.signal = serialized.get('signal', None)
        self.short_interval = serialized.get('short_interval', None)
        self.long_interval = serialized.get('long_interval', None)
        self.method = serialized.get('method', None)


    def set_auto_signal(signal_average, signal_offset=None, signal_noise=None):
        """Set the signal threshold automatically from observed parameters.

        @param signal_average int average signal level.
        @param signal_offset int amount to adjust the average by.
        @param signal_noise int amount of background noise observed.

        """
        signal = signal_average
        if signal_offset:
            signal += signal_offset
        if signal_noise:
            # Compensate for real noise vs standard estimate
            signal -= 95 + signal_noise
        logging.debug('Setting signal via auto configuration: '
                      'avg=%d, offset=%r, noise=%r => signal=%d.',
                      signal_average, signal_offset, signal_noise, signal)
        self.signal = signal
