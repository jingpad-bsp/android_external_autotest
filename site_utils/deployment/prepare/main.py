#!/usr/bin/env python
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to (re)prepare a DUT for lab deployment.

TODO(this docstring is a stub).
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging

import  common
from autotest_lib.site_utils.deployment.prepare import dut as preparedut

def main():
  opts = _parse_args()
  # Setup tempfile to capture trash dropped by autotest?
  # Setup logging to avoid dumping everything to stdout?
  logging.basicConfig(level=logging.DEBUG)

  host = preparedut.create_host(
      opts.hostname, opts.board, opts.model, opts.servo_hostname,
      opts.servo_port, opts.servo_serial)

  if 'stage-usb' in opts.actions:
    preparedut.download_image_to_servo_usb(host, opts.build)
  if 'install-firmware' in opts.actions:
    preparedut.install_firmware(host)
  if 'install-test-image' in opts.actions:
    preparedut.install_test_image(host)


def _parse_args():
  parser = argparse.ArgumentParser(
      description='Prepare / validate DUT for lab deployment.')

  parser.add_argument(
      'actions',
      nargs='+',
      choices=['stage-usb', 'install-firmware', 'install-test-image'],
      help='DUT preparation actions to execute.',
  )
  parser.add_argument(
      '--hostname',
      required=True,
      help='Hostname of the DUT to prepare.',
  )

  parser.add_argument(
      '--board',
      required=True,
      help='Board label of the DUT to prepare.',
  )
  parser.add_argument(
      '--model',
      required=True,
      help='Model label of the DUT to prepare.',
  )
  parser.add_argument(
      '--build',
      required=True,
      help='Chrome OS image version to use for installation.',
  )

  parser.add_argument(
      '--servo-hostname',
      required=True,
      help='Hostname of the servo host connected to the DUT.',
  )
  parser.add_argument(
      '--servo-port',
      required=True,
      help='Servo host port (to be) used for the controlling servo.',
  )
  parser.add_argument(
      '--servo-serial',
      help='Serial number of the controlling servo.',
  )

  return parser.parse_args()


if __name__ == '__main__':
  main()
