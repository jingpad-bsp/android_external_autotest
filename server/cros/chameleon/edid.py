# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import operator
import os


class Edid(object):
    """Edid is an abstraction of EDID (Extended Display Identification Data).

    It provides methods to get the properties, manipulate the structure,
    import from a file, export to a file, etc.

    """

    BLOCK_SIZE = 128


    def __init__(self, data, skip_verify=False):
        """Construct an Edid.

        @param data: A byte-array of EDID data.
        @param skip_verify: True to skip the correctness check.
        """
        if not Edid.verify(data) and not skip_verify:
            raise ValueError('Not a valid EDID.')
        self.data = data


    @staticmethod
    def verify(data):
        """Verify the correctness of EDID.

        @param data: A byte-array of EDID data.

        @return True if the EDID is correct; False otherwise.
        """
        data_len = len(data)
        if data_len % Edid.BLOCK_SIZE != 0:
            logging.debug('EDID has an invalid length: %d', data_len)
            return False

        for start in xrange(0, data_len, Edid.BLOCK_SIZE):
            # Each block (128-byte) has a checksum at the last byte.
            checksum = reduce(operator.add,
                              map(ord, data[start:start+Edid.BLOCK_SIZE]))
            if checksum % 256 != 0:
                logging.debug('Wrong checksum in the block %d of EDID',
                              start / Edid.BLOCK_SIZE)
                return False

        return True


    @classmethod
    def from_file(cls, filename):
        """Construct an Edid from a file.

        @param filename: A string of filename.
        """
        if not os.path.exists(filename):
            raise ValueError('EDID file %r does not exist' % filename)

        data = open(filename).read()
        return cls(data)


    def to_file(self, filename):
        """Export the EDID to a file.

        @param filename: A string of filename.
        """
        with open(filename, 'w+') as f:
            f.write(self.data)
