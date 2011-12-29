#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration for cell emulator tests."""
import copy, unittest

CELLS = {}

# TODO(rochberg):  Need some way to subset this list for long/short tests

GENERIC_GSM_TECHNOLOGIES = ['GPRS', 'EGPRS', 'WCDMA', 'HSDPA', 'HDUPA',
                            'HSDUPA', 'HSPA_PLUS',]

GOBI_2000_TECHNOLOGIES = GENERIC_GSM_TECHNOLOGIES + ['CDMA_2000', 'EVDO_1X']


def combine_trees(a_original, b):
    """Combines two dict-of-dict trees, favoring the second."""
    try:
        a = copy.copy(a_original)
        for (key_b, value_b) in b.iteritems():
            a[key_b] = combine_trees(a.get(key_b, None), value_b)
    except AttributeError:  # one argument wasn't a dict.  B wins.
        return b
    return a


def MakeDefault8960(specifics):
    base = {
            "type": "8960-prologix",
            # IP addresses and netmask for the air-side of the
            # basestation network.
            "bs_addresses": [
                "192.168.2.2",
                "192.168.2.3"
                ],
            "bs_netmask": "255.255.0.0",

            "gpib_adapter": {
                "gpib_address": 14,
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
    return combine_trees(base, specifics)


CELLS['cam'] = {
    "basestations": [
        MakeDefault8960({
            "gpib_adapter": {
                "ip_address": "172.31.206.171",
                },
            })
        ],
    "duts": [
        {
            "address": "172.31.206.145",
            "name": "ad-hoc-usb",
            "technologies": GOBI_2000_TECHNOLOGIES,
            },
        {
            "address": "172.31.206.146",
            "name": "y3300",
            "technologies": GENERIC_GSM_TECHNOLOGIES,
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


CELLS['mtv'] = {
    "basestations": [
        MakeDefault8960({
            "gpib_adapter": {
              "ip_address": "172.22.50.118",
              }
            })
        ],

    "duts": [
        {
            "address": "172.22.50.132",
            "name": "alex-gobi-2000",
            "technologies": GOBI_2000_TECHNOLOGIES,
            },
        ],

    # Used for tests that check web connectivity
    "http_connectivity": {
        "url": "http://172.22.50.118",
        # Check for the redirect to the auth page
        "url_required_contents": '<a href="http://172.22.73.6/afe">',
        },
    }


class TestCombineTrees(unittest.TestCase):
  def test_simple(self):
    self.assertEqual({1:2, 3:4, 5:6},
                     combine_trees({1:2, 3:4}, {5:6}))

  def test_override_simple(self):
    self.assertEqual({1:3},
                     combine_trees({1:2},{1:3}))

  def test_join_nested(self):
    self.assertEqual({1:{2:3, 3:4}},
                     combine_trees({1:{2:3}},{1:{3:4}}))

  def test_override_in_nested(self):
    self.assertEqual({1:{2:4}},
                     combine_trees({1:{2:3}},{1:{2:4}}))

  def test_override_different_types(self):
    self.assertEqual({1:{2:4}},
                     combine_trees({1:'rhinoceros'},{1:{2:4}}))
    self.assertEqual({1:'rhinoceros'},
                     combine_trees({1:{2:4}},{1:'rhinoceros'}))

  def test_two_level(self):
      self.assertEqual({1:{2:{3:4, 5:6}}},
                       combine_trees({1:{2:{3:4}}},{1:{2:{5:6}}}))

  def test_none(self):
      self.assertEqual({1:None},
                       combine_trees({1:2}, {1:None}))
      self.assertEqual({1:None},
                       combine_trees({1:None}, {}))
      self.assertEqual({1:2},
                       combine_trees({1:None}, {1:2}))


if __name__ == '__main__':
  unittest.main()
