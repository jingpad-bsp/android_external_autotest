#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import hashlib
import optparse
import os
import sys
import tempfile


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


def change_gbb_on_bios(old_bios, components):
    """
    Returns a new bios file that is changed its GBB values from old_bios
    according to the fields in components.

    Args:
        old_bios: BIOS file to be changed its GBB values.
        components: hardware component list to be referred.
    """
    for key in ['part_id_hwqual', 'data_bitmap_fv', 'key_root', 'key_recovery']:
        if len(components[key]) != 1 or components[key][0] == '*':
            raise Exception("Component list should have a valid value on %s" %
                            key)
    (fd, new_bios) = tempfile.mkstemp()
    cmd = 'gbb_utility --set'
    cmd += ' --hwid="%s"' % components['part_id_hwqual'][0]
    cmd += ' --bmpfv="%s"' % components['data_bitmap_fv'][0]
    cmd += ' --rootkey="%s"' % components['key_root'][0]
    cmd += ' --recoverykey="%s"' % components['key_recovery'][0]
    cmd += ' %s' % old_bios
    cmd += ' %s' % new_bios
    cmd += ' >/dev/null'
    if os.system(cmd) != 0:
        raise Exception("Fail to run gbb_utility: %s", cmd)
    return new_bios


def main():
    usage = 'Usage: %prog --target=BIOS|EC --image=IMAGE [--gbb=COMPONENTS]'
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--target', dest='target', metavar='BIOS|EC',
        help='hash target, BIOS or EC')
    parser.add_option('--image', dest='image',
        help='firmware image file, or empty to read system flashrom')
    parser.add_option('--gbb', dest='gbb', metavar='COMPONENTS',
        help='component file to be referred to replace GBB values in BIOS')
    (options, args) = parser.parse_args()

    image = options.image
    if image is None:
        parser.error("Please specify --image to a firmware image file or ''")

    target = options.target and options.target.lower()
    if target not in ['bios', 'ec']:
        parser.error("Please specify either BIOS or EC for --target")

    modified_image = None
    if options.gbb:
        if target != 'bios':
            parser.error("Please set --target=BIOS if replace GBB")
        if image == '':
            parser.error("Please specify --image to a file if replace GBB")
        components = eval(open(options.gbb).read())
        modified_image = change_gbb_on_bios(image, components)

    if target == 'bios':
        print get_bios_ro_hash(modified_image or image)
    elif target == 'ec':
        print get_ec_hash(image)

    # Remove the temporary GBB-modified file.
    if modified_image:
        os.remove(modified_image)


if __name__ == "__main__":
    main()
