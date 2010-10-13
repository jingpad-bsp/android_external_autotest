#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import hashlib
import sys


# This file may be shared by autotest framework and some command line tools
# setting PYTHONPATH, so we need to try different importing paths here.
try:
    from autotest_lib.client.common_lib import flashrom_util
    from autotest_lib.client.common_lib import site_fmap
except ImportError:
    # try to load from pre-defined PYTHONPATH
    import flashrom_util
    import site_fmap


def get_bios_ro_hash(file_source=None, exception_type=Exception):
    """
    Returns a hash of Read Only (BIOS) firmware parts,
    to confirm we have proper keys / boot code / recovery image installed.

    Args:
        file_source: None to read BIOS from system flash rom, or any string
        value as the file name of firmware image to read.
    """
    # hash_ro_list: RO section to be hashed
    hash_src = ''
    hash_ro_list = ['FV_BSTUB', 'FV_GBB', 'FVDEV']

    flashrom = flashrom_util.FlashromUtility()
    flashrom.initialize(flashrom.TARGET_BIOS, target_file=file_source)

    image = flashrom.get_current_image()
    fmap_obj = site_fmap.fmap_decode(image)
    if not fmap_obj:
        raise exception_type('No FMAP structure in flashrom.')

    # XXX Allowing the FMAP to override our default layout may be an exploit
    # here, because vendor can provide fake (non-used) GBB/BSTUB in unused
    # area.  However since the flash memory layout may change, we need to
    # trust FMAP here.
    # TODO(hungte) we can check that FMAP must reside in RO section, and the
    # BSTUB must be aligned to bottom of firmware.
    hash_src = hash_src + site_fmap.fmap_encode(fmap_obj)

    for section in hash_ro_list:
        src = flashrom.read_section(section)
        if not src:
            raise exception_type('Cannot get section [%s] from flashrom' %
                                  section)
        hash_src = hash_src + src
    if not hash_src:
        raise exception_type('Invalid hash source from flashrom.')

    return hashlib.sha256(hash_src).hexdigest()


def get_ec_hash(file_source=None, exception_type=Exception):
    """
    Returns a hash of Embedded Controller firmware parts,
    to confirm we have proper updated version of EC firmware.

    Args:
        file_source: None to read BIOS from system flash rom, or any string
        value as the file name of firmware image to read.
    """
    flashrom = flashrom_util.FlashromUtility()
    flashrom.initialize(flashrom.TARGET_EC, target_file=file_source)
    # to bypass the 'skip verification' sections
    image = flashrom.get_current_image()
    if not image:
        raise exception_type('Cannot read EC firmware')
    hash_src = flashrom.get_verification_image(image)
    return hashlib.sha256(hash_src).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) == 3:

        target = sys.argv[1].lower()
        target_file = sys.argv[2]
        if target_file == '':
            target_file = None

        if target == 'bios':
            print get_bios_ro_hash(target_file)
            sys.exit(0)
        elif target == 'ec':
            print get_ec_hash(target_file)
            sys.exit(0)

    # error
    print "Usage: %s TARGET FILE\n" % (sys.argv[0])
    print "TARGET: EC or BIOS"
    print "FILE:   a firmware image file, or '' to read system flashrom"
    sys.exit(1)
