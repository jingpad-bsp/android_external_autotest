#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test iperf parser."""

import unittest
import iperf


class test_iperf(unittest.TestCase):
    def test_parse_warning(self):
        text = """
WARNING: option -b implies udp testing
WARNING: option -b is not valid for server mode
------------------------------------------------------------
Client connecting to 172.31.206.152, UDP port 5001
Sending 1470 byte datagrams
UDP buffer size: 0.11 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 39777 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0-15.0 sec  1.88 MBytes  1.05 Mbits/sec
[  3] Sent 1339 datagrams
[  3] Server Report:
[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0-15.0 sec  1.88 MBytes  1.05 Mbits/sec  0.011 ms    1/ 1340 (0.075%)
""".lstrip().rstrip()
        self.assertRaises(iperf.Error, iperf.ParseIperfOutput, text)

    def test_connect_failed(self):
        text = """connect failed: Connection refused
------------------------------------------------------------
Client connecting to 172.31.206.152, TCP port 5001
TCP window size: 0.02 MByte (default)
------------------------------------------------------------
write1 failed: Broken pipe
[  3] local 0.0.0.0 port 57288 connected with 172.31.206.152 port 5001
write2 failed: Broken pipe
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 0.0 sec  0.00 MBytes  0.00 Mbits/sec
""".lstrip().rstrip()
        self.assertRaises(iperf.Error, iperf.ParseIperfOutput, text)

    def test_bad_udp(self):
        text = """------------------------------------------------------------
Client connecting to 172.31.206.152, UDP port 5001
Sending 1470 byte datagrams
UDP buffer size: 0.11 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 51532 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 5.2 sec  0.06 MBytes  0.10 Mbits/sec
[  3] Sent 44 datagrams
[  3] Server Report:

[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0- 5.2 sec  0.06 bogus  0.10 Mbits/sec  0.014 ms    1/   45 (2.2%)
""".lstrip().rstrip()
        self.assertRaises(iperf.Error, iperf.ParseIperfOutput, text)

    def test_udp(self):
        text = """------------------------------------------------------------
Client connecting to 172.31.206.152, UDP port 5001
Sending 1470 byte datagrams
UDP buffer size: 0.11 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 51532 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 5.2 sec  0.06 MBytes  0.10 Mbits/sec
[  3] Sent 44 datagrams
[  3] Server Report:
[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0- 5.2 sec  0.06 MBytes  0.10 Mbits/sec  0.014 ms    1/   45 (2.2%)
""".lstrip().rstrip()
        self.assertEqual({'jitter': 0.014,
                          'throughput': 100000,
                          'lost': 2.2},
                         iperf.ParseIperfOutput(text))

    def test_tcp(self):
        text = """------------------------------------------------------------
Client connecting to 172.31.206.152, TCP port 5001
TCP window size: 0.02 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 38376 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.0 sec  34.1 MBytes  95.4 Mbits/sec""".lstrip().rstrip()
        self.assertEqual({'throughput': 95.4e6}, iperf.ParseIperfOutput(text))

    def test_K(self):
         text = """------------------------------------------------------------
Client connecting to 172.31.206.152, TCP port 5001
TCP window size: 0.02 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 38376 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.0 sec  34.1 MBytes  95.4 Kbits/sec""".lstrip().rstrip()
         self.assertEqual({'throughput': 95400}, iperf.ParseIperfOutput(text))


if __name__ == '__main__':
    unittest.main()
