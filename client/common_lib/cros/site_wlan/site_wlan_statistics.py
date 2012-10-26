#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Monitor various interface statistics and create a histogram

This script monitors data from various debugfs sources to generate
a time series histogram of device activity.  The script can be set
up to take a certain number of samples, or to run "infinitely",
printing out a report when it receives a kill signal or the sample
count is acquired.

"""

import glob
import optparse
import re
import sys
import time
import signal

class SampleReader(object):
    def __init__(self):
        self.last_attributes = self.GetAttributes()
        self.data = []

    def GetDelta(self):
        attributes = self.GetAttributes()
        deltas = {}
        for attr in attributes:
            deltas[attr] = attributes[attr] - self.last_attributes[attr]
        self.last_attributes = attributes
        self.data.append(deltas)

    def Summarize(self):
        for attr in sorted(self.last_attributes.keys()):
            lineparts = [attr]
            for datum in self.data:
                lineparts.append(str(datum[attr]))
            print ','.join(lineparts)

class Ath9kSamplesReader(SampleReader):
    def __init__(self):
        dirs = glob.glob('/sys/kernel/debug/ieee80211/*/ath9k')
        self.dir = dirs[0] if len(dirs) > 0 else None

        self.files = {
            'recv': {
                'rx_crc': re.compile(' *CRC ERR : *(\d+)'),
                'rx_decrypt_crc_err':  re.compile(' *DECRYPT CRC ERR : *(\d+)'),
                'rx_phy_err':  re.compile(' *PHY ERR : *(\d+)'),
                'rx_pkts':  re.compile(' *RX-Pkts-All : *(\d+)'),
                'rx_bytes':  re.compile(' *RX-Bytes-All : *(\d+)'),
                },
            'xmit': {
                'tx_pkts':  re.compile(
                    ' *TX-Pkts-All: *(\d+) *(\d+) *(\d+) *(\d+)'),
                'tx_bytes':  re.compile(
                    ' *TX-Bytes-All: *(\d+) *(\d+) *(\d+) *(\d+)'),
                }
            }
        SampleReader.__init__(self)

    def IsValid(self):
        return bool(self.dir)

    def GetAttributes(self):
        if not self.dir:
            return
        attrs = {}
        for filename, re_hash in self.files.iteritems():
            for line in file('%s/%s' % (self.dir, filename)):
                for key, exp in re_hash.iteritems():
                    match = exp.match(line)
                    if match:
                        attrs[key] = sum(map(int, match.groups()))
        return attrs


# Used for testing
class DummyReader(SampleReader):
    def __init__(self):
        self.x = 1
        self.y = 1
        SampleReader.__init__(self)

    def IsValid(self):
        return True

    def GetAttributes(self):
        self.x += 1
        self.y *= 2
        return {'x': self.x, 'y': self.y}


class SigHandler(object):
    def __init__(self, reader):
        self.reader = reader
        self.printed = False

    def trigger(self, signum, frame):
        self.reader.Summarize()
        sys.exit(0)


def main(argv):
  parser = optparse.OptionParser('Usage: %prog [options...]')
  parser.add_option('--count', dest='count', type='int',
                    default=-1, help='Number of samples (-1 == infinite)')
  parser.add_option('--period', dest='period', type='int',
                    default=5, help='Period (in seconds) between samples')
  (options, args) = parser.parse_args(argv[1:])

  reader = None
  for reader_class in [Ath9kSamplesReader]:
      test_reader = reader_class()
      if test_reader.IsValid():
          reader = test_reader
          break

  if not reader:
      print>>sys.stderr, 'No devices available for statistics capture'
      return

  signal.signal(signal.SIGINT, SigHandler(reader).trigger)
  signal.signal(signal.SIGTERM, SigHandler(reader).trigger)

  count = options.count
  while count != 0:
      time.sleep(options.period)
      reader.GetDelta()
      count -= 1

  reader.Summarize()

if __name__ == '__main__':
  main(sys.argv)
