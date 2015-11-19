#!/usr/bin/python3.4

# Copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import queue

from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

from acts.utils import get_current_epoch_time

import acts.controllers.android_device as android_device
import acts.test_utils.wifi_test_utils as utils


class Map(dict):
    """A convenience class that makes dictionary values accessible via dot
    operator.

    Example:
        >> m = Map({"SSID": "GoogleGuest"})
        >> m.SSID
        GoogleGuest
    """
    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v
        if kwargs:
            for k, v in kwargs.items():
                self[k] = v


    def __getattr__(self, attr):
        return self.get(attr)


    def __setattr__(self, key, value):
        self.__setitem__(key, value)


class XmlRpcServerError(Exception):
    """Raised when an error is encountered in the XmlRpcServer."""


class RequestHandler(SimpleXMLRPCRequestHandler):
    """The RPC request handler used by SimpleXMLRPCServer.
    """
    rpc_paths = ('/RPC2',)


class AndroidXmlRpcDelegate:
    """Exposes methods called remotely during WiFi autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XMLRPC server.
    """

    DEFAULT_TEST_PROFILE_NAME = 'test'
    DBUS_DEVICE = 'Device'
    WEP40_HEX_KEY_LEN = 10
    WEP104_HEX_KEY_LEN = 26


    def __init__(self, serial_number):
        if not serial_number:
            ads = android_device.get_all_instances()
            if not ads:
                msg = "No android device found, abort!"
                logging.error(msg)
                raise XmlRpcServerError(msg)
            self.ad = ads[0]
        elif serial_number in android_device.list_adb_devices():
            self.ad = android_device.AndroidDevice(serial)
        else:
            msg = ("Specified Android device %s can't be found, abort!"
                   ) % serial_number
            logging.error(msg)
            raise XmlRpcServerError(msg)


    def __enter__(self):
        self.ad.get_droid()
        self.ad.ed.start()
        return self


    def __exit__(self, exception, value, traceback):
        self.ad.terminate_all_sessions()


    # Commands start.
    def ready(self):
        logging.debug("ready.")


    def list_controlled_wifi_interfaces(self):
        return ['wlan0']


    def set_device_enabled(self, wifi_interface, enabled):
        return True


    def sync_time_to(self, epoch_seconds):
        self.ad.droid.setTime(epoch_seconds)
        return True


    def clean_profiles(self):
        return True


    def create_profile(self, profile_name):
        return True


    def push_profile(self, profile_name):
        return True


    def remove_profile(self, profile_name):
        return True


    def pop_profile(self, profile_name):
        return True


    def disconnect(self, ssid):
        return True


    def delete_entries_for_ssid(self, ssid):
        try:
            utils.wifi_forget_network(self.ad, ssid)
        except Exception as e:
            logging.error(str(e))
            return False
        return True


    def connect_wifi(self, raw_params):
        """Block and attempt to connect to wifi network.

        @param raw_params serialized AssociationParameters.
        @return serialized AssociationResult
        """
        # Prepare data objects.
        params = Map(raw_params)
        params.security_config = Map(raw_params['security_config'])
        params.bgscan_config = Map(raw_params['bgscan_config'])
        logging.debug('connect_wifi(). Params: %r' % params)
        network_config = {
            "SSID": params.ssid,
            "hiddenSSID":  True if params.is_hidden else False
        }
        assoc_result = {
            "discovery_time" : 0,
            "association_time" : 0,
            "configuration_time" : 0,
            "failure_reason" : "Oops!",
            "xmlrpc_struct_type_key" : "AssociationResult"
        }
        try:
            # Scan for the network.
            start_time = get_current_epoch_time()
            self.ad.droid.wifiStartScan()
            self.ad.ed.pop_event("WifiManagerScanResultsAvailable",
                                 params.discovery_timeout)
            scan_results = self.ad.droid.wifiGetScanResults()
            end_time = get_current_epoch_time()
            assoc_result["discovery_time"] = (end_time - start_time) / 1000
            result = False
            # Verify that the network was found, if the SSID is not hidden.
            if not params.is_hidden:
                found = False
                for r in scan_results:
                    if "SSID" in r and r["SSID"] == params.ssid:
                        found = True
                assert found, "Could not find %s in scan results" % params.ssid
            if params.security_config.security == "psk":
                network_config["password"] = params.security_config.psk
            elif params.security_config.security == "wep":
                network_config["wepTxKeyIndex"] = params.security_config.wep_default_key
                # Convert all ASCII keys to Hex
                wep_hex_keys = []
                for key in params.security_config.wep_keys:
                    if len(key) == self.WEP40_HEX_KEY_LEN or \
                       len(key) == self.WEP104_HEX_KEY_LEN:
                        wep_hex_keys.append(key)
                    else:
                        hex_key = ""
                        for byte in bytes(key, 'utf-8'):
                            hex_key += '%x' % byte
                        wep_hex_keys.append(hex_key)
                network_config["wepKeys"] = wep_hex_keys
            # Associate to the network.
            self.ad.droid.wifiStartTrackingStateChange()
            start_time = get_current_epoch_time()
            result = self.ad.droid.wifiConnect(network_config)
            assert result, "wifiConnect call failed."
            # Verify connection successful and correct.
            logging.debug('wifiConnect result: %s. Waiting for connection' % result);
            timeout = params.association_timeout + params.configuration_timeout
            connect_result = self.ad.ed.pop_event(
                utils.WifiEventNames.WIFI_CONNECTED, timeout)
            end_time = get_current_epoch_time()
            assoc_result["association_time"] = (end_time - start_time) / 1000
            actual_ssid = connect_result['data'][utils.WifiEnums.SSID_KEY]
            logging.debug('Connected to SSID: %s' % params.ssid);
            assert actual_ssid == params.ssid, ("Expected to connect to %s, "
                "connected to %s") % (params.ssid, actual_ssid)
            result = True
        except queue.Empty:
            msg = "Failed to connect to %s with %s" % (params.ssid,
                params.security_config.security)
            logging.error(msg)
            assoc_result["failure_reason"] = msg
            result = False
        except Exception as e:
            msg = str(e)
            logging.error(msg)
            assoc_result["failure_reason"] = msg
            result = False
        finally:
            assoc_result["success"] = result
            logging.debug(assoc_result)
            self.ad.droid.wifiStopTrackingStateChange()
            return assoc_result


    def init_test_network_state(self):
        """Create a clean slate for tests with respect to remembered networks.

        @return True iff operation succeeded, False otherwise.
        """
        try:
            utils.wifi_test_device_init(self.ad)
        except AssertionError as e:
            logging.error(str(e))
            return False
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cros Wifi Xml RPC server.')
    parser.add_argument('-s', '--serial-number', action='store', default=None,
                         help='Serial Number of the device to test.')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("android_xmlrpc_server main...")
    server = SimpleXMLRPCServer(('localhost', 9989), allow_none=True,
        requestHandler=RequestHandler, logRequests=True, encoding="utf-8")
    server.register_introspection_functions()
    with AndroidXmlRpcDelegate(args.serial_number) as funcs:
        server.register_instance(funcs)
        server.serve_forever()