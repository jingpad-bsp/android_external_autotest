#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration for cell emulator tests."""

CELLS = {}

CELLS['cam'] = {
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
                "192.168.2.254",
                "192.168.2.254"
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
    # Routerstation pro for runing iperf
    "perfserver": {
        "address": "172.31.206.152",
        "name": "rspro-cros-2",
        "rf_address": "192.168.2.254"
        },
    # Used for tests that check web connectivity
    "http_connectivity": {
        "url": "http://192.168.2.254/index.html",
        "url_required_contents": "Chromium",
        },
    "rf_switch": {
        "type": "ether_io",
        "address":  "172.31.206.172",
        # Ports maps from port index to name as specified in
        # clients.name
        "ports": ['y3300', None, None, 'ad-hoc-usb'],
        }
    }
