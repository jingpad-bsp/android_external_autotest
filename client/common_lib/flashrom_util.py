# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This library provides convenience routines to access Flash ROM (EEPROM)

flashrom_util is based on utility 'flasrom'.

Original tool syntax:
    (read ) flashrom -r <file>
    (write) flashrom -l <layout_fn> [-i <image_name> ...] -w <file>

The layout_fn is in format of
    address_begin:address_end image_name
    which defines a region between (address_begin, address_end) and can
    be accessed by the name image_name.

Currently the tool supports multiple partial write but not partial read.

In the flashrom_util, we provide read and partial write abilities.
For more information, see help(flashrom_util.flashrom_util).
"""

import os
import warnings

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


# flashrom utility wrapper
class flashrom_util(object):
    """ a wrapper for "flashrom" utility.

    You can read, write, or query flash ROM size with this utility.
    Although you can do "partial-write", the tools always takes a
    full ROM image as input parameter.

    NOTE before accessing flash ROM, you may need to first "select"
    your target - usually BIOS or EC. That part is not handled by
    this utility. Please find other external script to do it.

    To perform a read, you need to:
     1. Prepare a flashrom_util object
        ex: flashrom = flashrom_util.flashrom_util()
     2. Perform read operation
        ex: image = flashrom.read_whole()

    To perform a (partial) write, you need to:
     1. Create or load a layout map (see explain of layout below)
        ex: layout_map = { 'all': (0, rom_size - 1) }
        ex: layout_map = { 'ro': (0, 0xFFF), 'rw': (0x1000, rom_size-1) }
     2. Prepare a full base image
        ex: image = flashrom.read_whole()
        ex: image = chr(0xFF) * rom_size
     3. (optional) Modify data in base image
        ex: new_image = flashrom.put_section(image, layout_map, 'all', mydata)
     4. Perform write operation
        ex: flashrom.write_partial(new_image, layout_map, ('all',))

     P.S: you can also create the new_image in your own way, for example:
        rom_size = flashrom_util.get_size()
        erase_image = chr(0xFF) * rom_size
        flashrom.write_partial(erase_image, layout_map, ('all',))

    The layout is a dictionary of { 'name': (address_begin, addres_end) }.
    Note that address_end IS included in the range.

    Attributes:
        tool_path:  file path to the tool 'flashrom'
        tmp_root:   a folder for temporary files (created for layout and images)
        tmp_prefix: prefix of file names
        verbose:    print debug and helpful messages
        keep_temp_files: boolean flag to control cleaning of temporary files
    """

    def __init__(self,
                 tool_path='/usr/sbin/flashrom',
                 tmp_root='/tmp',
                 tmp_prefix='fr_',
                 verbose=False,
                 keep_temp_files=False):
        """ constructor of flashrom_util. help(flashrom_util) for more info """
        self.tool_path = tool_path
        self.tmp_root = tmp_root
        self.tmp_prefix = tmp_prefix
        self.verbose = verbose
        self.keep_temp_files = keep_temp_files

    def get_temp_filename(self, prefix):
        ''' (internal) Returns name of a temporary file in self.tmp_root '''
        with warnings.catch_warnings():
            # although tempnam is not safe, it's OK to use here for testing.
            warnings.simplefilter("ignore")
            return os.tempnam(self.tmp_root, self.tmp_prefix + prefix)

    def remove_temp_file(self, filename):
        """ (internal) Removes a temp file if self.keep_temp_files is false. """
        if self.keep_temp_files:
            return
        if os.path.exists(filename):
            os.remove(filename)

    def create_layout_file(self, layout_map):
        '''
        (internal) Creates a layout file based on layout_map.
        Returns the file name containing layout information.
        '''
        layout_text = [ '0x%08lX:0x%08lX %s' % (v[0], v[1], k)
            for k, v in layout_map.items() ]
        layout_text.sort()  # XXX unstable if range exceeds 2^32
        tmpfn = self.get_temp_filename('lay')
        open(tmpfn, 'wb').write('\n'.join(layout_text) + '\n')
        return tmpfn

    def get_section(self, base_image, layout_map, section_name):
        '''
        Retrieves a section of data based on section_name in layout_map.
        Raises error if unknown section or invalid layout_map.
        '''
        pos = layout_map[section_name]
        if pos[0] >= pos[1] or pos[1] >= len(base_image):
            raise error.TestError('INTERNAL ERROR: invalid layout map.')
        return base_image[pos[0] : pos[1] + 1]

    def put_section(self, base_image, layout_map, section_name, data):
        '''
        Updates a section of data based on section_name in layout_map.
        Raises error if unknown section or invalid layout_map.
        Returns the full updated image data.
        '''
        pos = layout_map[section_name]
        if pos[0] >= pos[1] or pos[1] >= len(base_image):
            raise error.TestError('INTERNAL ERROR: invalid layout map.')
        if not (len(data) == pos[1] - pos[0] + 1):
            raise error.TestError('INTERNAL ERROR: unmatched data size.')
        return base_image[0 : pos[0]] + data + base_image[pos[1] + 1 :]

    def get_size(self):
        """ Gets size of current flash ROM """
        # TODO(hungte) Newer version of tool (flashrom) may support --get-size
        # command which is faster in future. Right now we use back-compatible
        # method: read whole and then get length.
        image = self.read_whole()
        return len(image)

    def read_whole(self):
        '''
        Reads whole flash ROM data.
        Returns the data read from flash ROM, or empty string for other error.
        '''
        tmpfn = self.get_temp_filename('rd_')
        cmd = '%s -r %s' % (self.tool_path, tmpfn)
        if self.verbose:
            print 'flashrom_util.read_whole(): ', cmd
        result = ''

        if utils.system(cmd, ignore_status=True) == 0:  # failure for non-zero
            try:
                result = open(tmpfn, 'rb').read()
            except IOError:
                result = ''

        # clean temporary resources
        self.remove_temp_file(tmpfn)
        return result

    def write_partial(self, base_image, layout_map, write_list):
        '''
        Writes data in sections of write_list to flash ROM.
        Returns True on success, otherwise False.
        '''
        tmpfn = self.get_temp_filename('wr_')
        open(tmpfn, 'wb').write(base_image)
        layout_fn = self.create_layout_file(layout_map)

        cmd = '%s -l %s -i %s -w %s' % (
                self.tool_path, layout_fn, ' -i '.join(write_list), tmpfn)
        if self.verbose:
            print 'flashrom.write_partial(): ', cmd
        result = False

        if utils.system(cmd, ignore_status=True) == 0:  # failure for non-zero
            result = True

        # clean temporary resources
        self.remove_temp_file(tmpfn)
        self.remove_temp_file(layout_fn)
        return result


if __name__ == "__main__":
    print "please invoke this script within autotest."
