# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from math import fabs

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.site_wlan import constants
from autotest_lib.server.cros import time_util
from autotest_lib.server.cros.wlan import api_shim


class ConnectException(Exception):
    """Base class for connection exceptions."""
    pass


class ConnectFailed(Exception):
    """Raised when a call to tell the DUT to connect fails."""
    pass


class ConnectTimeout(Exception):
    """Raised when a call to tell the DUT to connect takes too long."""
    pass


class Connector(api_shim.ApiShim):
    """Enables remotely ordering a DUT to connect to wifi.

    Currently implemented in terms of scripts in
    client/common_lib/cros/site_wlan.  This API should evolve together
    with the refactor of those scripts to provide an RPC interface to
    drive connectivity on DUTs: http://crosbug.com/35757
    """
    def __init__(self, host):
        super(Connector, self).__init__(host)


    @classmethod
    def _script_name(cls):
        """Returns the name of the script this class wraps."""
        return 'site_wlan_connect.py'


    def connect(self, ssid, security='', psk=''):
        """Attempts to connect client to AP.

        @param ssid: String formatted ssid.
        @param security: One of '', 'wep', 'psk'.
        @param psk: The passphrase if security is not ''.

        @raises ValueError if psk does not accompany non-'' value for security.
        @raises ConnectFailed upon failure.
        @raises ConnectTimeout if attempt takes more time than is allotted.

        @raises AutoservRunError: if the wrapped command failed.
        @raises AutoservSSHTimeout: ssh connection has timed out.
        """
        if security and not psk:
            raise ValueError('Passing security=%s requires a value for psk.')
        result = self._client.run('python "%s" "%s" "%s" "%s" "%d" "%d" '
                                  '--hidden' %
                                  (self._script,
                                   ssid, security, psk,
                                   constants.DEFAULT_TIMEOUT_SECONDS,
                                   constants.DEFAULT_TIMEOUT_SECONDS),
                                  ignore_status=True)
        # These codes are taken from main() in site_wlan_connect.py.
        if result.exit_status == 2:
            raise ConnectFailed(result.stdout)
        elif result.exit_status == 3:
            raise ConnectTimeout(result.stdout)

class TracingConnector(Connector):
    """ Connector that preforms a packet trace given a packet_capture object.

    A wrapper for Connector that will perform a trace.
    """

    DEFAULT_BANDWIDTH='HT40+'
    # Maximum tolerable clock skew in second.
    MAX_OFFSET_IN_SECOND=float(1.0)

    def __init__(self, host, capturer,
                 max_offset_in_sec=MAX_OFFSET_IN_SECOND):
        """ Initialization.

        @param host: Hostname/ip of the client device running the test.
        @param capturer: A packet_capture instance.
        @param max_offset_in_sec: A float, number of seconds.
        """
        super(TracingConnector, self).__init__(host)
        self.capturer = capturer
        self.trace_frequency = None
        self.trace_bandwidth = self.DEFAULT_BANDWIDTH
        self.trace_filename = None

        self._host = host
        if not self._clocks_are_in_sync(max_offset_in_sec):
            # Attempt to force a clock sync on both DUT and tracer.
            self._force_tlsdate_restart()
            logging.debug('Completed tlsdate restart on both DUT and tracer.')

            self._clocks_are_in_sync(max_offset_in_sec, raise_error=True)

    def set_frequency(self, frequency):
        """ Set the frequency with which to capture from.

        @param frequency:  An integer indicating the capture frequency.
        """
        self.trace_frequency = frequency


    def set_bandwidth(self, bandwidth=None):
        """ Set the bandwidth with which to capture with.

        @param bandwidth: A string representing the bandwidth.
        """
        if bandwidth:
            self.trace_bandwidth = bandwidth
        else:
            self.trace_bandwidth = self.DEFAULT_BANDWIDTH


    def set_filename(self, filename):
       """ Set the filename.

       The following strings are appended to the filename based on the
       connection status: _success.trc or _fail.trc

       @param filename: The file with which to store the capture.
       """
       self.trace_filename = filename


    def connect(self, ssid, security='', psk='', frequency=None,
                bandwidth=None):
        """ Wrapper around connect with packet capturing

        @param ssid: String formatted ssid.
        @param security: One of '', 'wep', 'psk'.
        @param psk: The passphrase if security is not ''.
        """

        self.set_frequency(frequency)
        self.set_bandwidth(bandwidth)
        success = True
        try:
            self.capturer.start_capture(self.trace_frequency,
                                        self.trace_bandwidth)
            super(TracingConnector, self).connect(ssid, security, psk)
        except (ConnectFailed, ConnectTimeout) as e:
            success = False
        finally:
            self.capturer.stop_capture()
            if success:
                filename = self.trace_filename + '_success.trc'
            else:
                filename = self.trace_filename + '_fail.trc'
            self.capturer.get_capture_file(filename)
            if not success:
                raise e

    def _get_clock_skew_in_sec(self):
        """ Both DUT and tracer rely on 'tlsdated' to synchronize their clocks.

        Even if either or both go out of sync with the remote time server,
        we can still proceed with the test so long as their clocks are
        reasonably in sync with each other.

        @returns a float, clock skew in seconds.

        @raises TestError: if unable to fetch datetime data from device.
        """
        # Get time elapsed since epoch in <seconds>.<nanoseconds>
        dut_time_epoch_sec = time_util.get_datetime_float(self._host)
        logging.debug('DUT time is %f sec.', dut_time_epoch_sec)

        tracer_time_epoch_sec = self.capturer.get_datetime_float()
        logging.debug('Tracer time is %f sec.', tracer_time_epoch_sec)

        return fabs(dut_time_epoch_sec - tracer_time_epoch_sec)

    def _force_tlsdate_restart(self):
        """ Invokes 'tlsdate restart' command on both DUT and tracer. """
        time_util.force_tlsdate_restart(self._host)
        self.capturer.force_tlsdate_restart()

    def _clocks_are_in_sync(self, max_offset_in_sec, raise_error=False):
        """ Check if DUT and tracer are synchronized in time.

        @param max_offset_in_sec: a float, max. allowed clock skew in seconds.
        @param raise_error: a boolean, True == raise error.

        @returns a boolean, True == clocks in sync.

        @raises TestError: if clocks out of sync and raise_error == True.
        """
        clock_skew_in_sec = self._get_clock_skew_in_sec()
        logging.info('Clock skew is %f sec.', clock_skew_in_sec)
        clocks_in_sync = clock_skew_in_sec < max_offset_in_sec
        if not clocks_in_sync and raise_error:
            err = ('Clocks on DUT and packet tracer are out of sync '
                   '(skew = %f sec, max permitted = %f sec)' %
                   (clock_skew_in_sec, max_offset_in_sec))
            raise error.TestError(err)
        return clocks_in_sync
