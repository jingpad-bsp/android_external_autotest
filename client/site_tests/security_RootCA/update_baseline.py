#!/usr/bin/env python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A script to update "baseline" with new openssl roots.

Usage:
  ./add_openssl_roots.py ./baseline.json /path/to/new/roots/

This reads the NSS store from baseline, updates the openssl section with certs
from /path/to/new/certs, and updates the diffs between NSS and openssl. It
updates the baseline file in place.

/path/to/new/roots can be the unpacked certificate directory from
app-misc/ca-certificates, or
chroot/build/${BOARD}/usr/share/ca-certificates/mozilla/ if you have emerged the
upgraded package for ${BOARD}.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import glob
import json
import os
import subprocess
import sys

from format_baseline import dump_baseline


SSL_CMD = ['openssl', 'x509', '-fingerprint', '-noout', '-in']


def get_nss_store(baseline_file):
  """Parses baseline for the NSS store."""
  with open(baseline_file) as f:
    baseline = json.load(f)

  nss_store = baseline['nss'].copy()
  nss_store.update(baseline['both'])
  return nss_store


def get_openssl_store(certs_dir):
  """Gets the new openssl store that should be updated to."""
  openssl_store = {}
  for cert in glob.glob(os.path.join(certs_dir, '*.crt')):
    cn = os.path.basename(cert)  # certs are named after their common names
    cn = cn.replace('_', ' ').replace('.crt', '')
    fingerprint = subprocess.check_output(
        SSL_CMD + [cert]).strip().partition('=')[2]
    openssl_store[fingerprint.decode('utf-8')] = cn.decode('utf-8')
  return openssl_store


def store_diff(store_a, store_b):
  """Returns certs in store_a but not store_b."""
  fingerprints_a = set(store_a.keys())
  fingerprints_b = set(store_b.keys())
  a_min_b = fingerprints_a - fingerprints_b
  return dict((fingerprint, store_a[fingerprint]) for fingerprint in a_min_b)


def store_common(store_a, store_b):
  """Returns certs in both stores."""
  fingerprints_a = set(store_a.keys())
  fingerprints_b = set(store_b.keys())
  a_and_b = fingerprints_a & fingerprints_b
  return dict((fingerprint, store_a[fingerprint]) for fingerprint in a_and_b)


def parse_args(argv):
  """Parses command line arguments."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('baseline', default='./baseline.json',
                      help='Path to baseline file')
  parser.add_argument('rootsdir',
                      help='Directory to the openssl certs to be installed')
  opts = parser.parse_args(argv)
  return opts


def main(argv):
  """The main function."""
  opts = parse_args(argv)
  nss_store = get_nss_store(opts.baseline)
  openssl_store = get_openssl_store(opts.rootsdir)

  new_baseline = {
      u'both': store_common(openssl_store, nss_store),
      u'nss': store_diff(nss_store, openssl_store),
      u'openssl': store_diff(openssl_store, nss_store),
  }
  serialized = dump_baseline(new_baseline)
  with open(opts.baseline, 'w') as f:
    f.write(serialized)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
