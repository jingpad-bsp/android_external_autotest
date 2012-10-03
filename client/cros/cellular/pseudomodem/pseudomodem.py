#!/usr/bin/env python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

USAGE = """

  Run pseudomodem to simulate a modem using the modemmanager-next
  DBus interfaces.

  Use --help for info.

"""

import logging
import optparse


DEFAULT_CARRIER = 'Banana Cellular'

def Start(options):
    # TODO(armansito): create modem according to options, with
    # appropriate carrier name. Create pseudo network
    # interface, modemmanager, add modem to manager,
    # run glib loop
    raise NotImplementedError()

def main():
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option('-c', '--carrier', dest='carrier_name',
                      default=DEFAULT_CARRIER,
                      metavar='<carrier name>',
                      help='<carrier name> := anything')
    parser.add_option('-l', '--logfile', dest='logfile',
                      default=None,
                      metavar='<filename>',
                      help='<filename> := filename for logging output')
    parser.add_option('-t', '--technology', dest='tech',
                      default='GSM',
                      metavar='<technology>',
                      help='<technology> := GSM|CDMA|LTE')

    options = parser.parse_args()[0]

    logging.basicConfig(format='%(asctime)-15s %(message)s',
                        level=logging.DEBUG,
                        filename=options.logfile)

    Start(options)


if __name__ == '__main__':
    main()
