# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util


class hardware_EepromWriteProtect(test.test):
    """
    Autotest for EEPROM Write Protection status
    """
    version = 1
    pre_post_exec_dir = '/usr/share/flashrom'
    verbose = True

    def setup(self):
        """ autotest setup procedure """
        # TODO(hungte) if the flashrom layout/script becomes a new ebuild,
        #              we will enable following dependency.
        # self.job.setup_dep(['flashrom_utils'])
        self.flashrom = flashrom_util.flashrom_util(verbose=self.verbose)

    def check_write_protection(self, layout_map, write_list, expected):
        '''
        The complete procedure to check write protection status.
        '''
        # write-protection testing procedure:
        #  1. perform read (expected: success)
        #  2. create a new image as different data (can be garbage) for writing
        #  3. perform write to image created in (2)
        #  4. perform read again for verification
        #  5. compare write tool return value in (3) with expected result
        #     (ro: write failure, rw: write success)
        #  6. restore flashrom by re-writing original image from (1) if required
        #     (by comparing image in (4) and (1))

        flashrom = self.flashrom  # for quick access
        original_image = flashrom.read_whole()
        if not original_image:
            raise error.TestError('Cannot read valid flash rom data.')

        # build a different image to write.
        write_image = original_image
        for section in write_list:
            data = flashrom.get_section(original_image, layout_map, section)
            # to make each byte different, we reverse it (xor 0xff).
            data = ''.join([chr(ord(c) ^ 0xFF) for c in data])
            write_image = flashrom.put_section(write_image, layout_map,
                                               section, data)
        if write_image == original_image:
            raise error.TestError('INTERNAL ERROR: failed to build image data')

        # standard procedure: write, read (for verify), and restore if changed.
        write_status = flashrom.write_partial(write_image,
                                              layout_map, write_list)
        verify_result = flashrom.read_whole()
        if not (verify_result == original_image):
            flashrom.write_partial(original_image, layout_map, write_list)

        # compile flags to simplify logic, and build result messages
        is_data_changed = not (verify_result == original_image)
        is_data_changed_correctly = (verify_result == write_image)

        if write_status:
            tool_msg = 'SUCCESS'
            expected_tool_msg = 'failure'
        else:
            tool_msg = 'FAILURE'
            expected_tool_msg = 'success'

        if not is_data_changed:
            changed_msg = 'not changed'
        elif is_data_changed_correctly:
            changed_msg = 'changed'
        else:
            changed_msg = 'changed to incorrect data'

        # report the analyzed results
        if write_status == expected:
            # expected result from tool, now verify the data.
            if write_status == is_data_changed:
                return True
            else:
                raise error.TestError(
                        'Tool returns %s to write operation as expected but '
                        'the physical data on EEPROM is %s. '
                        'Please check system consistency.' %
                        (tool_msg, changed_msg))
        else:
            # unexpected result from tool, try to give suggestion
            if write_status == is_data_changed:
                # tool works correctly. should be caused by EEPROM.
                suggest = 'Please check EEPROM write-protection status.'
            else:
                suggest = 'Please check tool behavior (eg, layout table)'
            raise error.TestFail(
                    'Tool returns %s to write operation (expected: %s). '
                    'EEPROM content is %s. %s' %
                    (tool_msg, expected_tool_msg, changed_msg, suggest))

    def exec_pre_post(self, conf, exec_type):
        """ Executes a pre/post execution command """
        if not exec_type in conf:
            return True
        # invoke pre/post-execution script
        exec_fn = os.path.join(self.pre_post_exec_dir, conf[exec_type])
        if not os.path.exists(exec_fn):
            raise error.TestError('INTERNAL ERROR: '
                    'missing %s script for %s: %s. ' %
                    (exec_type, conf['name'], exec_fn))
        utils.system(exec_fn)
        return True

    def build_layout_map(self, layout_desc, flashrom_size):
        """
        Parses a layout description string and build corresponding map.
        layout_map is a dictionary of section_name:(address_begin, address_end)
        ro_list and rw_list are lists of readonly / readwrite section names.

        Returns (layout_map, ro_list, rw_list).
        """
        layout_list = layout_desc.split(',')
        block_size = flashrom_size / len(layout_list)
        layout_map = {}
        ro_list = []
        rw_list = []
        iblk = 0

        for attr in layout_list:
            pos = (iblk * block_size, (iblk + 1) * block_size - 1)
            name = 's%02d%s' % (iblk, attr)
            iblk = iblk + 1
            layout_map[name] = pos

            if attr == 'ro':
                ro_list.append(name)
            elif attr == 'rw':
                rw_list.append(name)
            elif attr == 'skip':
                pass
            else:
                raise error.TestError('INTERNAL ERROR: '
                        'unknown layout attribute (%s).' % attr)
        return (layout_map, ro_list, rw_list)

    def run_once(self):
        """ core testing procedure """
        # the EEPROM should be programmed as:
        #     (BIOS)  LSB [ RW | RO ] MSB
        #     (EC)    LSB [ RO | RW ] MSB
        #  because CPU starts execution from high address while EC starts
        #  from low level address.
        #  Also each part of RW/RO section occupies half of the EEPROM.
        eeprom_sets = (
            { # BIOS
                'name': 'BIOS',
                'layout': 'rw,ro',
                'pre_exec': 'select_bios_flashrom.sh',
                'post_exec': 'select_bios_flashrom.sh',
            }, { # embedded controller
                'name': 'EC', # embedded controller
                'layout': 'ro,rw',
                'pre_exec': 'select_ec_flashrom.sh',
                'post_exec':'select_bios_flashrom.sh',
            }, )

        # print os.getcwd()
        for conf in eeprom_sets:
            # pre-exection (for initialization like flash rom selection)
            self.exec_pre_post(conf, 'pre_exec')

            # build layout
            flashrom_size = self.flashrom.get_size()
            (layout_map, ro_list, rw_list) = self.build_layout_map(
                    conf['layout'], flashrom_size)
            # ro test
            if self.verbose:
                print ' - RO testing %s: %s' % (conf['name'], ','.join(ro_list))
            self.check_write_protection(layout_map, ro_list, False)
            # rw test
            if self.verbose:
                print ' - RW testing %s: %s' % (conf['name'], ','.join(rw_list))
            self.check_write_protection(layout_map, rw_list, True)
            # post-execution (for clean-up)
            self.exec_pre_post(conf, 'post_exec')


if __name__ == "__main__":
    print "please run this program with autotest."
