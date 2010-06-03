# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, os, re, string, sys, time
import dbus, dbus.mainloop.glib, gobject

class network_WiFiSmokeTest(test.test):
    version = 1

    def sanitize(self, ssid):
        return re.sub('[^a-zA-Z0-9_]', '_', ssid)


    def ConnectToNetwork(self, ssid, security, psk,
        assoc_timeout=15, config_timeout=15):

        """Attempts to connect to a network using FlimFlam."""

        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus(mainloop=bus_loop)
        manager = dbus.Interface(bus.get_object("org.chromium.flimflam", "/"),
            "org.chromium.flimflam.Manager")

        try:
            path = manager.GetService(({
                "Type": "wifi",
                "Mode": "managed",
                "SSID": ssid,
                "Security": security,
                "Passphrase": psk }))
            service = dbus.Interface(
                bus.get_object("org.chromium.flimflam", path),
                "org.chromium.flimflam.Service")
        except Exception, e:
            logging.info('FAIL(GetService): ssid %s exception %s', ssid, e)
            return 1

        try:
            service.Connect()
        except Exception, e:
            logging.info("FAIL(Connect): ssid %s exception %s", ssid, e)
            return 2

        status = ""
        assoc_time = 0
        # wait up to assoc_timeout seconds to associate
        while assoc_time < assoc_timeout:
            properties = service.GetProperties()
            status = properties.get("State", None)
            if status == "failure":
                logging.info("FAIL(assoc): ssid %s assoc %3.1f secs props %s",
                    ssid, assoc_time, properties)
                return 3
            if status == "configuration" or status == "ready":
                break
            time.sleep(.5)
            assoc_time += .5
        if assoc_time >= assoc_timeout:
            logging.info("TIMEOUT(assoc): ssid %s assoc %3.1f secs", ssid,
	        assoc_time)
            return 4

        self.write_perf_keyval({"secs_assoc_time_" +
            self.sanitize(ssid): assoc_time})

        # wait another config_timeout seconds to get an ip address
        config_time = 0
        if status != "ready":
            while config_time < config_timeout:
                properties = service.GetProperties()
                status = properties.get("State", None)
                if status == "failure":
                    logging.info("FAIL(config): ssid %s assoc %3.1f config "
		        "%3.1f secs", ssid, assoc_time, config_time)
                    return 5
                if status == "ready":
                    break
                time.sleep(.5)
                config_time += .5
            if config_time >= config_timeout:
                logging.info("TIMEOUT(config): ssid %s assoc %3.1f config "
		    "%3.1f secs", ssid, assoc_time, config_time)
                return 6

        self.write_perf_keyval({"secs_config_time_" +
            self.sanitize(ssid): config_time})

        logging.info('SUCCESS: ssid %s assoc %3.1f secs config %3.1f secs'
            ' status %s' %(ssid, assoc_time, config_time, status))
        return 0


    def run_once(self, wifi_router_list):
        fd = open(wifi_router_list)
        routers = eval(fd.read())

        passed = 0
        tried = 0
        for ssid, properties in routers.iteritems():
            tried += 1
            security = properties.get("security")
            psk = properties.get("psk", "")
            assoc_timeout = properties.get("assoc_timeout", 15)
            config_timeout = properties.get("config_timeout", 15)
            if self.ConnectToNetwork(ssid, security, psk, assoc_timeout,
                config_timeout) != 0:
                continue
            # ping server if configured
            ping_args = properties.get("ping_args", None)
            if ping_args is not None:
                if utils.system('ping %s' % ping_args, ignore_status=True) != 0:
                    logging.info('FAIL(ping): ssid %s ping %s'
                        % (ssid, ping_args))
                    continue;
                logging.info('SUCCESS: ssid %s ping %s' % (ssid, ping_args))
            passed += 1

        if tried == 0:
            raise error.TestFail("No tests were attempted")
        if passed == 0:
            raise error.TestFail("No tests passed")
        if passed != tried:
            raise error.TestFail("Tests failed: %d of %d"
                %(tried - passed, tried))
