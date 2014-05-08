# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from tempfile import NamedTemporaryFile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

TARGET_BIOS = 'bios'
TARGET_EC = 'ec'

FMAP_AREA_NAMES = (
    'name',
    'offset',
    'size',
)

EXPECTED_FMAP_TREE_BIOS = {
  'WP_RO': {
    'RO_SECTION': {
      'FMAP': {},
      'GBB': {},
      'RO_FRID': {},
    },
    'RO_VPD': {},
  },
  'RW_SECTION_A': {
    'VBLOCK_A': {},
    'FW_MAIN_A': {},
    'RW_FWID_A': {},
  },
  'RW_SECTION_B': {
    'VBLOCK_B': {},
    'FW_MAIN_B': {},
    'RW_FWID_B': {},
  },
  'RW_VPD': {},
}

EXPECTED_FMAP_TREE_EC = {
  'WP_RO': {
    'EC_RO': {
      'FMAP': {},
      'RO_FRID': {},
    },
  },
  'EC_RW': {
    'RW_FWID': {},
  },
}

class FMap(object):
    """Provides access to firmware FMap.

    Attributes:

    @attr _target: Target of firmware, either TARGET_BIOS or TARGET_EC.
    @attr _areas: List of dicts containing area names, offsets, and sizes.
    """

    _TARGET_PROGRAMMERS = {
        TARGET_BIOS: '-p internal:bus=spi',
        TARGET_EC: '-p internal:bus=lpc',
    }

    def __init__(self, target=None):
        self._target = target or TARGET_BIOS
        self._areas = None


    def is_flash_available(self):
        """Is the flash chip available?"""
        return utils.system("flashrom --flash-name %s" % self._target,
                            ignore_status=True) == 0


    def get_areas(self):
        """Get a list of dicts containing area names, offsets, and sizes.

        It fetches the FMap data from the active firmware via flashrom and
        dump_fmap. Caches the result in self._areas.
        """
        if not self._areas:
            with NamedTemporaryFile(prefix='fw_%s_' % self._target) as f:
                utils.system("flashrom %s -r %s -i FMAP" % (
                        self._TARGET_PROGRAMMERS[self._target],
                        f.name))
                lines = utils.system_output("dump_fmap -p %s" % f.name)
            # The above output is formatted as:
            # name1 offset1 size1
            # name2 offset2 size2
            # ...
            # Convert it to a list of dicts like:
            # [{'name': name1, 'offset': offset1, 'size': size1},
            #  {'name': name2, 'offset': offset2, 'size': size2}, ...]
            self._areas = [dict(zip(FMAP_AREA_NAMES, line.split()))
                           for line in lines.split('\n') if line.strip()]
        return self._areas


    def _is_bounded(self, region, bounds):
        """Is the given region bounded by the given bounds?"""
        return ((bounds[0] <= region[0] < bounds[1]) and
                (bounds[0] < region[1] <= bounds[1]))


    def _is_overlapping(self, region1, region2):
        """Is the given region1 overlapping region2?"""
        return (min(region1[1], region2[1]) > max(region1[0], region2[0]))


    def check_areas(self, areas, expected_tree, bounds=None):
        """Check the given area list met the hierarchy of the expected_tree.

        It checks all areas in the expected tree are existed and non-zero sized.
        It checks all areas in sub-trees are bounded by the region of the root
        node. It also checks all areas in child nodes are mutually exclusive.

        @param areas: A list of dicts containing area names, offsets, and sizes.
        @param expected_tree: A hierarchy dict of the expected FMap tree.
        @param bounds: The boards that all areas in the expect_tree are bounded.
                       If None, ignore the bounds check.

        >>> f = FMap()
        >>> a = [{'name': 'FOO', 'offset': 100, 'size': '200'},
        ...      {'name': 'BAR', 'offset': 100, 'size': '50'},
        ...      {'name': 'ZEROSIZED', 'offset': 150, 'size': '0'},
        ...      {'name': 'OUTSIDE', 'offset': 50, 'size': '50'}]
        ...      {'name': 'OVERLAP', 'offset': 120, 'size': '50'},
        >>> f.check_areas(a, {'FOO': {}})
        True
        >>> f.check_areas(a, {'NOTEXISTED': {}})
        False
        >>> f.check_areas(a, {'ZEROSIZED': {}})
        False
        >>> f.check_areas(a, {'BAR': {}, 'OVERLAP': {}})
        False
        >>> f.check_areas(a, {'FOO': {}, 'BAR': {}})
        False
        >>> f.check_areas(a, {'FOO': {}, 'OUTSIDE': {}})
        True
        >>> f.check_areas(a, {'FOO': {'BAR': {}}})
        True
        >>> f.check_areas(a, {'FOO': {'OUTSIDE': {}}})
        False
        >>> f.check_areas(a, {'FOO': {'NOTEXISTED': {}}})
        False
        >>> f.check_areas(a, {'FOO': {'ZEROSIZED': {}}})
        False
        """
        succeed = True
        checked_regions = []
        for branch in expected_tree:
            area = next((a for a in areas if a['name'] == branch), None)
            if not area:
                logging.error("The area %s is not existed.", branch)
                succeed = False
                continue
            region = [int(area['offset']),
                      int(area['offset']) + int(area['size'])]
            if int(area['size']) == 0:
                logging.error("The area %s is zero-sized.", branch)
                succeed = False
            elif bounds and not self._is_bounded(region, bounds):
                logging.error("The region %s [%d, %d) is out of the bounds "
                              "[%d, %d).", branch, region[0], region[1],
                              bounds[0], bounds[1])
                succeed = False
            elif any(r for r in checked_regions if self._is_overlapping(
                    region, r)):
                logging.error("The area %s is overlapping others.", branch)
                succeed = False
            elif not self.check_areas(areas, expected_tree[branch], region):
                succeed = False
            checked_regions.append(region)
        return succeed


class firmware_FMap(test.test):
    """Client-side FMap test.

    This test checks the active BIOS and EC firmware contains the required
    FMap areas and verifies their hierarchies. It relies on flashrom to dump
    the active BIOS and EC firmware and dump_fmap to decode them.
    """
    version = 1

    def run_once(self):
        f = FMap(TARGET_BIOS)
        if not f.check_areas(f.get_areas(), EXPECTED_FMAP_TREE_BIOS):
            raise error.TestFail("BIOS FMap is not qualified.")

        f = FMap(TARGET_EC)
        if f.is_flash_available():
            if not f.check_areas(f.get_areas(), EXPECTED_FMAP_TREE_EC):
                raise error.TestFail("EC FMap is not qualified.")
        else:
            logging.warning("EC is not available on this device.")
