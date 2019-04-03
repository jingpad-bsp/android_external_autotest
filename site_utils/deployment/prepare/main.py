#!/usr/bin/env python
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to (re)prepare a DUT for lab deployment."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging
import logging.config
import os

import common
from autotest_lib.site_utils.deployment.prepare import dut as preparedut

def main():
  """Tool to (re)prepare a DUT for lab deployment."""
  opts = _parse_args()
  _configure_logging('prepare_dut', os.path.join(opts.results_dir, _LOG_FILE))

  uart_logs_dir = os.path.join(opts.results_dir, _UART_LOGS_DIR)
  os.makedirs(uart_logs_dir)

  with preparedut.create_host(
      opts.hostname, opts.board, opts.model, opts.servo_hostname,
      opts.servo_port, opts.servo_serial, uart_logs_dir) as host:

    if opts.dry_run:
      logging.info('DRY RUN: Would have run actions %s', opts.actions)
      return

    if 'stage-usb' in opts.actions:
      preparedut.download_image_to_servo_usb(host, opts.build)
    if 'install-firmware' in opts.actions:
      preparedut.install_firmware(host, opts.force_firmware)
    if 'install-test-image' in opts.actions:
      preparedut.install_test_image(host)


_LOG_FILE = 'prepare_dut.log'
_UART_LOGS_DIR = 'uart'


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
      '--dry-run',
      action='store_true',
      default=False,
      help='Run in dry-run mode. No changes will be made to the DUT.',
  )
  parser.add_argument(
      '--results-dir',
      required=True,
      help='Directory to drop logs and output artifacts in.',
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
  parser.add_argument(
      '--force-firmware',
      action='store_true',
      help='Force firmware isntallation via chromeos-installfirmware.',
  )

  return parser.parse_args()


def _configure_logging(name, tee_file):
    """Configure logging globally.

    @param name: Name to prepend to log messages.
                 This should be the name of the program.
    @param tee_file: File to tee logs to, in addition to stderr.
    """
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'stderr': {
                'format': ('{name}: '
                           '%(asctime)s:%(levelname)s'
                           ':%(module)s:%(funcName)s:%(lineno)d'
                           ': %(message)s'
                           .format(name=name)),
            },
            'tee_file': {
                'format': ('%(asctime)s:%(levelname)s'
                           ':%(module)s:%(funcName)s:%(lineno)d'
                           ': %(message)s'),
            },
        },
        'handlers': {
            'stderr': {
                'class': 'logging.StreamHandler',
                'formatter': 'stderr',
            },
            'tee_file': {
                'class': 'logging.FileHandler',
                'formatter': 'tee_file',
                'filename': tee_file,
            },
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['stderr', 'tee_file'],
        },
        'disable_existing_loggers': False,
    })


if __name__ == '__main__':
  main()
