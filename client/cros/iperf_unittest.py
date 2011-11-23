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
        expected = {'jitter': 0.014,
                    'throughput': 100000.0,
                    'lost': 2.2}
        expected.update(dict([('uplink_' + a, b)
                              for (a,b) in expected.items()]))
        self.assertEqual(expected,
                         iperf.ParseIperfOutput(text))


    def test_udp_tradeoff(self):
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
------------------------------------------------------------
Server listening on UDP port 5001
Receiving 1470 byte datagrams
UDP buffer size:   110 KByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 5001 connected with 172.31.206.152 port 57416
[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0- 3.0 sec    386 KBytes  1.05 Mbits/sec  0.085 ms    1/  270 (0.37%)
""".lstrip().rstrip()
        expected = {'jitter': 0.014,
                    'throughput': 100000.0,
                    'lost': 2.2}
        expected.update(dict([('uplink_' + a, b)
                              for (a,b) in expected.items()]))
        expected.update({'downlink_throughput': 1.05e6,
                         'downlink_jitter': 0.085,
                         'downlink_lost': 0.37})

        self.assertEqual(expected,
                         iperf.ParseIperfOutput(text))



    def test_tcp(self):
        text = """------------------------------------------------------------
Client connecting to 172.31.206.152, TCP port 5001
TCP window size: 0.02 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 38376 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.0 sec  34.1 MBytes  95.4 Mbits/sec""".lstrip().rstrip()
        self.assertEqual({'throughput': 95.4e6,
                          'uplink_throughput': 95.4e6},
                         iperf.ParseIperfOutput(text))
    def test_tcp_tradeoff(self):
        text = """------------------------------------------------------------
Client connecting to 172.31.206.152, TCP port 5001
TCP window size: 0.02 MByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 38376 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.0 sec  34.1 MBytes  95.4 Mbits/sec
------------------------------------------------------------
Server listening on TCP port 5001
TCP window size: 85.3 KByte (default)
------------------------------------------------------------
[  4] local 172.31.206.145 port 5001 connected with 172.31.206.152 port 56542
[ ID] Interval       Transfer     Bandwidth
[  4]  0.0- 3.0 sec  34.1 MBytes  94.7 Mbits/sec""".lstrip().rstrip()
        self.assertEqual({'throughput': 95.4e6,
                          'uplink_throughput': 95.4e6,
                          'downlink_throughput': 94.7e6},
                         iperf.ParseIperfOutput(text))


    def test_Multipliers(self):
        self.assertEqual(1, iperf.ParseMultiplier(1, 'bits/sec'))
        self.assertEqual(1, iperf.ParseMultiplier('1', 'bits/sec'))
        self.assertEqual(1000, iperf.ParseMultiplier('1', 'Kbits/sec'))
        self.assertEqual(1000000, iperf.ParseMultiplier('1', 'Mbits/sec'))
        self.assertEqual(1000000000, iperf.ParseMultiplier('1', 'Gbits/sec'))
        self.assertEqual(1000000000, iperf.ParseMultiplier('1000', 'Mbits/sec'))


if __name__ == '__main__':
    unittest.main()
