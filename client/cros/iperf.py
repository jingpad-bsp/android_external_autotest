#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build iperf command lines and parse iperf output.

Taken from site_wifitest.py."""

class Error(Exception):
    pass


def _BuildCommonArgs(params):
    common_args = ''
    perf = {}

    if 'udp' in params:
        common_args += ' -u'
        test = 'UDP'
    else:
        test = 'TCP'
    if 'nodelay' in params:
        common_args += ' -N'
        perf['nodelay'] = 'true'
    if 'window' in params:
        common_args += ' -w %s' % params['window']
        perf['window'] = params['window']
    common_args += ' -p 5001'
    return (common_args, perf)


def BuildClientCommand(server, params=None, command="/usr/local/bin/iperf"):
    """Builds commands to execute to start IPerf client.
    Args:
        params:  dict containing parameters described below.

    Returns:
        (client command, dictionary of perf keyvals)
    """
    if not params:
        params = {}
    (common_args, perf) = _BuildCommonArgs(params)

    # -c must come before -bandwidth or bandwidth won't be respected.
    # Stick it at the beginning.
    client_args = (' -c %s' % server +
                   common_args +
                   ' -t %s' % params.get('test_time', 15))

    if 'bandwidth' in params:
        if not 'udp' in params:
            raise Error("Specified bandwidth without UDP")
        client_args += ' -b %s' % params['bandwidth']
        perf['bandwidth'] = params['bandwidth']

    if 'tradeoff' in params:
        client_args += ' --tradeoff'

    return (command + client_args, perf)


def BuildServerCommand(params, command="/usr/bin/iperf"):
    (common_args, perf) = _BuildCommonArgs(params)
    return command + ' -s' + common_args


def ApplyMultiplier(quantity, multiplier):
    """Given a quantity and multiplier of 'Xbits/sec', return bits/sec."""

    MULTIPLIERS={
        'bits/sec': 1.0e0,
        'Kbits/sec': 1.0e3,
        'Mbits/sec': 1.0e6,
        'Gbits/sec': 1.0e9,
    }

    if multiplier not in MULTIPLIERS:
        raise Error('Could not parse multiplier %s' % multiplier)
    return float(quantity) * MULTIPLIERS[multiplier]


def _ParseOneTcpLine(line):
    """Parses a line of TCP output, returns bandwidth.
    Args:
        line:  a line like "[  3]  0.0- 5.2 sec  0.06 MBytes  0.10 Mbits/sec"
    """
    tcp_tokens = line.split()
    if len(tcp_tokens) >= 6 and 'bits/sec' in tcp_tokens[-1]:
        return ApplyMultiplier(tcp_tokens[-2], tcp_tokens[-1])
    else:
        raise Error('Could not parse TCP line')


def _ParseTcpOutput(lines):
    """Parses the following and returns a single dictionary with
    uplink throughput, and, if available, downlink throughput.

    ------------------------------------------------------------
    Client connecting to localhost, TCP port 5001
    TCP window size: 49.4 KByte (default)
    ------------------------------------------------------------
    [  3] local 127.0.0.1 port 57936 connected with 127.0.0.1 port 5001
    [ ID] Interval       Transfer     Bandwidth
    [  3]  0.0-10.0 sec  2.09 GBytes  1.79 Gbits/sec
    """
    perf = {}

    uplink = _ParseOneTcpLine(lines[6])
    perf['uplink_throughput'] = uplink
    if len(lines) > 13:
        perf['downlink_throughput'] = _ParseOneTcpLine(lines[13])

    return perf

def _ParseOneUdpLine(line, prefix):
    udp_tokens = line.replace('/', ' ').split()
    # Find the column ending with "...Bytes"
    mb_col = [col for col, data in enumerate(udp_tokens)
              if data.endswith('Bytes')]

    if len(mb_col) > 0 and len(udp_tokens) >= mb_col[0] + 9:
        # Make a sublist starting after the column named "MBytes"
        stat_tokens = udp_tokens[mb_col[0]+1:]
        # Rebuild Mbits/sec out of Mbits sec
        multiplier = '%s/%s' % tuple(stat_tokens[1:3])
        return {prefix + 'throughput':
                    ApplyMultiplier(stat_tokens[0], multiplier),
                prefix + 'jitter':float(stat_tokens[3]),
                prefix + 'lost':float(stat_tokens[7].strip('()%'))}
    else:
        raise Error('Could not parse UDP line: %s' % line)



def _ParseUdpOutput(lines):
    """Parses iperf output, returns throughput, jitter, and loss.
------------------------------------------------------------
Client connecting to 172.31.206.152, UDP port 5001
Sending 1470 byte datagrams
UDP buffer size:   110 KByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 39460 connected with 172.31.206.152 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.0 sec    386 KBytes  1.05 Mbits/sec
[  3] Sent 269 datagrams
[  3] Server Report:
[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0- 3.0 sec    386 KBytes  1.05 Mbits/sec  0.010 ms    1/  270 (0.37%)
------------------------------------------------------------
Server listening on UDP port 5001
Receiving 1470 byte datagrams
UDP buffer size:   110 KByte (default)
------------------------------------------------------------
[  3] local 172.31.206.145 port 5001 connected with 172.31.206.152 port 57416
[ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
[  3]  0.0- 3.0 sec    386 KBytes  1.05 Mbits/sec  0.085 ms    1/  270 (0.37%)
"""
    byte_lines = [line for line in lines
                  if 'Bytes' in line]
    if len(byte_lines) < 2 or len(byte_lines) > 3:
        raise Error('Wrong number of byte report lines: %d' % len(byte_lines))

    out = _ParseOneUdpLine(byte_lines[1], 'uplink_')
    if len(byte_lines) > 2:
        out.update(_ParseOneUdpLine(byte_lines[2], 'downlink_'))

    return out

def ParseIperfOutput(input):
    if not isinstance(input, list):
        lines = input.split('\n')
        all_text = input
    else:
        lines = input
        all_text = '\n'.join(lines)

    if 'WARNING' in all_text:
        raise Error('Iperf results contained a WARNING: %s' % all_text)

    if 'Connection refused' in all_text:
        raise Error('Could not connect to iperf server')

    if 'TCP' in lines[1]:
        protocol = 'TCP'
    elif 'UDP' in lines[1]:
        protocol = 'UDP'
    else:
        raise Error('Could not parse header line %s' % lines[1])

    if protocol == 'TCP':
        return _ParseTcpOutput(lines)
    elif protocol == 'UDP':
        return _ParseUdpOutput(lines)
    else:
        raise Error('Unhandled protocol %s' % lines)
