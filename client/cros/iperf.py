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

    return (command + client_args, perf)


def BuildServerCommand(params, command="/usr/bin/iperf"):
    (common_args, perf) = _BuildCommonArgs(params)
    return command + ' -s' + common_args


MULTIPLIERS={
    'Kbits/sec': 1.0e3,
    'Mbits/sec': 1.0e6,
    'Gbits/sec': 1.0e9,
}


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

    perf = {}

    if protocol == 'TCP':
        """Parses the following and returns a single element dictionary
        with throughput value.

        ------------------------------------------------------------
        Client connecting to localhost, TCP port 5001
        TCP window size: 49.4 KByte (default)
        ------------------------------------------------------------
        [  3] local 127.0.0.1 port 57936 connected with 127.0.0.1 port 5001
        [ ID] Interval       Transfer     Bandwidth
        [  3]  0.0-10.0 sec  2.09 GBytes  1.79 Gbits/sec
        """
        tcp_tokens = lines[6].split()
        if len(tcp_tokens) >= 6 and tcp_tokens[-1] in MULTIPLIERS:
            return {'throughput':
                        MULTIPLIERS[tcp_tokens[-1]] * float(tcp_tokens[-2])}
        else:
            raise Error('Could not parse throughput line: %s' % lines[6])

    elif protocol == 'UDP':
        """Parses the following and returns a dictionary of performance values.

        ------------------------------------------------------------
        Client connecting to localhost, UDP port 5001
        Sending 1470 byte datagrams
        UDP buffer size:   108 KByte (default)
        ------------------------------------------------------------
        [  3] local 127.0.0.1 port 54244 connected with 127.0.0.1 port 5001
        [ ID] Interval       Transfer     Bandwidth
        [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec
        [  3] Sent 893 datagrams
        [  3] Server Report:
        [ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Da
        [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec  0.032 ms 1/894 (0.11%)
        [  3]  0.0-15.0 sec  14060 datagrams received out-of-order
        """
        # Search for the last row containing the word 'Bytes'
        mb_row = [row for row,data in enumerate(lines)
                  if 'Bytes' in data][-1]
        udp_tokens = lines[mb_row].replace('/', ' ').split()
        # Find the column ending with "...Bytes"
        mb_col = [col for col,data in enumerate(udp_tokens)
                  if data.endswith('Bytes')]
        if len(mb_col) > 0 and len(udp_tokens) >= mb_col[0] + 9:
            # Make a sublist starting after the column named "MBytes"
            stat_tokens = udp_tokens[mb_col[0]+1:]
            # Rebuild Mbits/sec out of Mbits sec
            multiplier = '%s/%s' % tuple(stat_tokens[1:3])
            if multiplier not in MULTIPLIERS:
                raise Error('Could not parse multiplier in %s' % mb_row)
            return {'throughput':
                        float(stat_tokens[0]) * MULTIPLIERS[multiplier],
                    'jitter':float(stat_tokens[3]),
                    'lost':float(stat_tokens[7].strip('()%'))}
        else:
            raise Error('Could not parse UDP test output: %s' % lines)
    else:
        raise Error('Unhandled protocol %s' % lines)
