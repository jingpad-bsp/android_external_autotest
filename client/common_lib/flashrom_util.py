#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This module provides convenience routines to access Flash ROM (EEPROM)

flashrom_util is based on utility 'flashrom'.

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
import sys
import tempfile


# simple layout description language compiler
def compile_layout(desc, size):
    """ compile_layout(desc, size) -> layout

    Compiles a flashrom layout by simple description language.
    Returns the result as a map. Empty map for any error.

    syntax:       <desc> ::= <partitions>
            <partitions> ::= <partition>
                           | <partitions> '|' <partition>
             <partition> ::= <spare_section>
                           | <partition> ',' <section>
                           | <section> ',' <partition>
               <section> ::= <name> '=' <size>
         <spare_section> ::= '*'
                           | <name>
                           | <name> '=' '*'

     * Example: 'ro|rw', 'ro=0x1000,*|*,rw=0x1000'
     * Each partition share same space from total size of flashrom.
     * Sections are fix sized, or "spare" which consumes all remaining
       space from a partition.
     * You can use any non-zero decimal or heximal (0xXXXX) in <size>.
       (size as zero is reserved now)
     * You can use '*' as <name> for "unamed" items which will be ignored in
       final layout output.
     * You can use "<name>=*" or simply "<name>" (including '*', the
       'unamed section') to define spare section.
     * There must be always one (no more, no less) spare section in
       each partition.
    """
    # create an empty layout first
    layout = {}
    err_ret = {}

    # prepare: remove all spaces (literal from string.whitespace)
    desc = ''.join([c for c in desc if c not in '\t\n\x0b\x0c\r '])
    # find equally-sized partitions
    parts = desc.split('|')
    block_size = size / len(parts)
    offset = 0

    for part in parts:
        sections = part.split(',')
        sizes = []
        names = []
        spares = 0

        for section in sections:
            # skip empty section to allow final ','
            if section == '':
                continue
            # format name=v or name ?
            if section.find('=') >= 0:
                k, v = section.split('=')
                if v == '*':
                    v = 0            # spare section
                else:
                    v = int(v, 0)
                    if v == 0:
                        raise TestError('Using size as 0 is prohibited now.')
            else:
                k, v = (section, 0)  # spare, should appear for only one.
            if v == 0:
                spares = spares + 1
            names.append(k)
            sizes.append(v)

        if spares != 1:
            # each partition should have exactly one spare field
            return err_ret

        spare_size = block_size - sum(sizes)
        sizes[sizes.index(0)] = spare_size
        # fill sections
        for i in range(len(names)):
            # ignore unamed sections
            if names[i] != '*':
                layout[names[i]] = (offset, offset + sizes[i] - 1)
            offset = offset + sizes[i]

    return layout


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
     2. Decide target (BIOS/EC)
        ex: flashrom.select_bios_flashrom()
     3. Perform read operation
        ex: image = flashrom.read_whole()

    To perform a (partial) write, you need to:
     1. Select target (BIOS/EC)
        ex: flashrom.select_ec_flashrom()
     2. Create or load a layout map (see explain of layout below)
        ex: layout_map = { 'all': (0, rom_size - 1) }
        ex: layout_map = { 'ro': (0, 0xFFF), 'rw': (0x1000, rom_size-1) }
        You can also use built-in layout like detect_chromeos_bios_layout(),
        detect_chromeos_layout(), or detect_layout() to build the layout maps.
     3. Prepare a full base image
        ex: image = flashrom.read_whole()
        ex: image = chr(0xFF) * rom_size
     4. (optional) Modify data in base image
        ex: new_image = flashrom.put_section(image, layout_map, 'all', mydata)
     5. Perform write operation
        ex: flashrom.write_partial(new_image, layout_map, ('all',))

     P.S: you can also create the new_image in your own way, for example:
        rom_size = flashrom_util.get_size()
        erase_image = chr(0xFF) * rom_size
        flashrom.write_partial(erase_image, layout_map, ('all',))

    The layout is a dictionary of { 'name': (address_begin, addres_end) }.
    Note that address_end IS included in the range.
    See help(detect_layout) for easier way to generate layout maps.

    Attributes:
        tool_path:  file path to the tool 'flashrom'
        cmd_prefix: prefix of every shell cmd, ex: "PATH=.:$PATH;export PATH;"
        tmp_root:   a folder name for mkstemp (for temp of layout and images)
        verbose:    print debug and helpful messages
        keep_temp_files: boolean flag to control cleaning of temporary files
        target_maps:maps of what commands should be invoked to switch target
    """

    # target selector command map syntax:
    # "arch" : { "target" : exec_script, ... }, ... }
    default_target_maps = {
        "i386": {
            # The magic numbers here are register indexes and values that apply
            # to all current known i386 based ChromeOS devices.
            # Detail information is defined in section #"10.1.50 GCS-General
            # Control and Status Register" of document "Intel NM10 Express
            # Chipsets".
            "bios": 'iotools mmio_write32 0xfed1f410 ' +
                    '`iotools mmio_read32 0xfed1f410 |head -c 6`0460',
            "ec":   'iotools mmio_write32 0xfed1f410 ' +
                    '`iotools mmio_read32 0xfed1f410 |head -c 6`0c60',
        },
    }

    default_chromeos_layout_desc = {
        "bios": """
                FV_LOG          = 0x20000,
                NV_COMMON_STORE = 0x10000,
                VBOOTA          = 0x02000,
                FVMAIN          = 0xB0000,
                VBOOTB          = 0x02000,
                FVMAINB         = 0xB0000,
                NVSTORAGE       = 0x10000,
                FV_RW_RESERVED  = *,
                |
                FV_RO_RESERVED  = *,
                FVDEV           = 0xB0000,
                FV_GBB          = 0x20000,
                FV_BSTUB        = 0x40000,
                """,
        "ec": """
                EC_RO
                |
                EC_RW
              """,
    }

    def __init__(self,
                 tool_path='/usr/sbin/flashrom',
                 cmd_prefix='',
                 tmp_root=None,
                 verbose=False,
                 keep_temp_files=False,
                 target_maps=None):
        """ constructor of flashrom_util. help(flashrom_util) for more info """
        self.tool_path = tool_path
        self.cmd_prefix = cmd_prefix
        self.tmp_root = tmp_root
        self.verbose = verbose
        self.keep_temp_files = keep_temp_files
        self.target_map = {}

        # determine bbs map
        if not target_maps:
            target_maps = self.default_target_maps
        if utils.get_arch() in target_maps:
            self.target_map = target_maps[utils.get_arch()]

    def get_temp_filename(self, prefix):
        ''' (internal) Returns name of a temporary file in self.tmp_root '''
        (fd, name) = tempfile.mkstemp(prefix=prefix, dir=self.tmp_root)
        os.close(fd)
        return name

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
        layout_text = ['0x%08lX:0x%08lX %s' % (v[0], v[1], k)
            for k, v in layout_map.items()]
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
            raise TestError('INTERNAL ERROR: invalid layout map.')
        return base_image[pos[0] : pos[1] + 1]

    def put_section(self, base_image, layout_map, section_name, data):
        '''
        Updates a section of data based on section_name in layout_map.
        Raises error if unknown section or invalid layout_map.
        Returns the full updated image data.
        '''
        pos = layout_map[section_name]
        if pos[0] >= pos[1] or pos[1] >= len(base_image):
            raise TestError('INTERNAL ERROR: invalid layout map.')
        if len(data) != pos[1] - pos[0] + 1:
            raise TestError('INTERNAL ERROR: unmatched data size.')
        return base_image[0 : pos[0]] + data + base_image[pos[1] + 1 :]

    def get_size(self):
        """ Gets size of current flash ROM """
        # TODO(hungte) Newer version of tool (flashrom) may support --get-size
        # command which is faster in future. Right now we use back-compatible
        # method: read whole and then get length.
        image = self.read_whole()
        return len(image)

    def detect_layout(self, layout_desciption, size=None):
        """
        Detects and builds layout according to current flash ROM size
        and a simple layout description language.
        If parameter 'size' is omitted, self.get_size() will be called.

        See help(flashrom_util.compile_layout) for the syntax of description.

        Returns the layout map (empty if any error).
        """
        if not size:
            size = self.get_size()
        return compile_layout(layout_desciption, size)

    def detect_chromeos_layout(self, target, size=None):
        """
        Detects and builds ChromeOS firmware layout according to current flash
        ROM size.  If parameter 'size' is None, self.get_size() will be called.

        Currently supported targets are: 'bios' or 'ec'.

        Returns the layout map (empty if any error).
        """
        if target not in self.default_chromeos_layout_desc:
            raise TestError('INTERNAL ERROR: unknown layout target: %s' % test)
        chromeos_target = self.default_chromeos_layout_desc[target]
        return self.detect_layout(chromeos_target, size)

    def detect_chromeos_bios_layout(self, size=None):
        """ Detects standard ChromeOS BIOS layout """
        return self.detect_chromeos_layout('bios', size)

    def detect_chromeos_ec_layout(self, size=None):
        """ Detects standard ChromeOS Embedded Controller layout """
        return self.detect_chromeos_layout('ec', size)

    def read_whole(self):
        '''
        Reads whole flash ROM data.
        Returns the data read from flash ROM, or empty string for other error.
        '''
        tmpfn = self.get_temp_filename('rd_')
        cmd = '%s"%s" -r "%s"' % (self.cmd_prefix, self.tool_path, tmpfn)
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

        cmd = '%s"%s" -l "%s" -i %s -w "%s"' % (
                self.cmd_prefix, self.tool_path,
                layout_fn, ' -i '.join(write_list), tmpfn)
        if self.verbose:
            print 'flashrom.write_partial(): ', cmd
        result = False

        if utils.system(cmd, ignore_status=True) == 0:  # failure for non-zero
            result = True

        # clean temporary resources
        self.remove_temp_file(tmpfn)
        self.remove_temp_file(layout_fn)
        return result

    def select_target(self, target):
        '''
        Selects (usually by setting BBS register) a target defined in target_map
        and then directs all further firmware access to certain region.
        '''
        if target not in self.target_map:
            return True
        if self.verbose:
            print 'flashrom.select_target("%s"): %s' % (target,
                                                        self.target_map[target])
        if utils.system(self.cmd_prefix + self.target_map[target],
                        ignore_status=True) == 0:
            return True
        return False

    def select_bios_flashrom(self):
        ''' Directs all further accesses to BIOS flash ROM. '''
        return self.select_target('bios')

    def select_ec_flashrom(self):
        ''' Directs all further accesses to Embedded Controller flash ROM. '''
        return self.select_target('ec')


# ---------------------------------------------------------------------------
# The flashrom_util supports both running inside and outside 'autotest'
# framework, so we need to provide some mocks and dynamically load
# autotest components here.


class mock_TestError(object):
    """ a mock for error.TestError """
    def __init__(self, msg):
        print msg
        sys.exit(1)


class mock_utils(object):
    """ a mock for autotest_li.client.bin.utils """
    def get_arch(self):
        arch = os.popen('uname -m').read().rstrip()
        arch = re.sub(r"i\d86", r"i386", arch, 1)
        return arch

    def system(self, cmd, ignore_status=False):
        ret = os.system(cmd)
        if (not ignore_status) and ret != 0:
            raise TestError("failed to execute: " % cmd)
        return ret


# import autotest or mock utilities
try:
    # print 'using autotest'
    from autotest_lib.client.bin import test, utils
    from autotest_lib.client.common_lib.error import TestError
except ImportError:
    # print 'using mocks'
    import re
    utils = mock_utils()
    TestError = mock_TestError


# main stub
if __name__ == "__main__":
    # TODO(hungte) provide unit tests or command line usage
    pass
