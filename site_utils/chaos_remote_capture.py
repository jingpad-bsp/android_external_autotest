#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse

import common
from autotest_lib.server import packet_capture

"""
Thin wrapper around PacketCapture to simplify taking packet captures from the
chaos lab remotely.  You can run this script outside the chroot to connect to
the chaos lab, allocate a packet capture machine, and take a capture of some
ongoing WiFi activity on a particular frequency and channel width.  After the
script finishes, it copies the pcap file back to your local machine for
analysis.

For example:
    ./chaos_remote_capture.py -f 5785 -c HT40+ -o my_output.cap

The script will take some time to set up, then begin capturing until you push
a key to end the capture.  If the script fails, check that you've specified a
valid WiFi channel frequency.  This isn't checked by the script except in the
sense that remote commands will fail without valid input.
"""

def capture_packets(frequency, channel_width, output_file):
    with packet_capture.PacketCaptureManager() as capturer:
        try:
            capturer.allocate_packet_capture_machine()
            capturer.start_capture(frequency, channel_width)
            raw_input("Press Enter to continue...")
        except error.TestError as e:
            raise e
        except Exception as e:
            logging.error('Problem: %s', str(e))

        finally:
            capturer.stop_capture()
            capturer.get_capture_file(output_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Trigger chaos lab packet captures from the comfort of '
                        'your workstation.',
            epilog='If this command fails for non-obvious reasons, '
                   'double-check that you have specified a valid frequency.')
    parser.add_argument('-f',
                        '--frequency',
                        required=True,
                        nargs=1,
                        type=int)
    parser.add_argument('-c',
                        '--channel_width',
                        required=True,
                        nargs=1,
                        type=str,
                        choices=['HT40+', 'HT40-', 'HT20'])
    parser.add_argument('-o',
                        '--output_file',
                        required=True,
                        nargs=1,
                        type=str)
    args = parser.parse_args()
    capture_packets(args.frequency[0],
                    args.channel_width[0],
                    args.output_file[0])
