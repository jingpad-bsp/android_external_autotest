#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Combo sample Cellular test cell config server and example config."""

import BaseHTTPServer
import json

cells = {
    "name": "cros-cam",
    "cells": [                  # A list of cells covered by this config file
        {
            "basestations": [
                {
                    # IP addresses and netmask for the air-side of the
                    # basestation network.
                    "bs_addresses": [
                        "192.168.2.2",
                        "192.168.2.3"
                    ],
                    "bs_netmask": "255.255.0.0",

                    "name": "8960-1",
                    "type": "8960-prologix",

                    "gpib_adapter": {
                        "gpib_address": 14,
                        "ip_address": "172.31.206.171",
                        "ip_port": 1234
                    },
                    # DNS addresses for the UE.  You do not need a
                    # working DNS server at this address, but you must
                    # have a machine there to send ICMP Port
                    # Unreachable messages, so the DNS lookups will
                    # fail quickly)
                    "ue_dns_addresses": [
                        "192.168.2.2",
                        "192.168.2.2"
                    ],
                    "ue_rf_addresses": [
                        "192.168.2.4",
                        "192.168.2.5"
                    ]
                }
            ],
            "clients": [
                {
                    "address": "172.31.206.145",
                    "name": "ad-hoc-usb"
                },
                {
                    "address": "172.31.206.146",
                    "name": "y3300"
                }
            ],
            # Routerstation pro for runing {i/net}perf
            "perfserver": {
                "address": "172.31.206.151",
                "name": "rspro-cros-1",
                "rf_address": "192.168.2.254"
            },
            # Used for tests that check web throughput and
            # connectivity
            "webserver": {
                "address": "192.168.2.1",
            },
            "rf_switch": {
                "type": "null"
            }
        }
    ]
}


class CellHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(s):
        s.send_response(200)
        s.end_headers()
        json.dump(cells, fp=s.wfile, sort_keys=True, indent=4)

    def address_string(self):
        # Do not attempt DNS reverse-lookups
        return self.client_address


PORT = 8081

if __name__ == '__main__':
    httpd = BaseHTTPServer.HTTPServer(("", PORT), CellHandler)
    print "serving at port", PORT
    httpd.serve_forever()
