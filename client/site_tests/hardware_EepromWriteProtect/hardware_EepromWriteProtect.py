# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import factory, test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flashrom_util, gpio


class hardware_EepromWriteProtect(test.test):
    """
    Autotest for EEPROM Write Protection status

    WARNING: DO NOT INTERRUPT THIS TEST OTHERWISE YOUR FLASHROM MAY BE CORRUPTED

    NOTE: This test only verifies write-protection status.
    If you want to enable write protection, run factory_EnableWriteProtect.
    """
    version = 2
    verbose = True

    def setup(self):
        """ autotest setup procedure """
        self.flashrom = flashrom_util.flashrom_util(verbose=self.verbose)
        self.gpio = gpio.Gpio(error.TestError)

    def check_gpio_write_protection(self):
        try:
            status_val = self.gpio.read('write_protect')
        except:
            raise error.TestFail('Cannot read GPIO Write Protection status.')
        if status_val != 1:
            raise error.TestFail('GPIO Write Protection is not enabled')

    def check_write_protection(self, layout_map, write_list, expected,
                               original_image):
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

        # build a different image to write.
        flashrom = self.flashrom  # for quick access
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
        self.gpio.setup()

        # quick check write protection by GPIO
        self.check_gpio_write_protection()

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
                'target': 'bios',
            }, { # embedded controller
                'name': 'EC', # embedded controller
                'layout': 'ro,rw',
                'target': 'ec',
            }, )

        # always restore system flashrom selection to this one
        system_default_selection = 'bios'
        print '\n\n!!!!! WARNING: DO NOT INTERRUPT THIS TEST      !!!!!'
        print '\n\n!!!!! OTHERWISE YOUR FIRMWARE MAY BE CORRUPTED !!!!!\n\n'
        factory.log('!!!!! WARNING: DO NOT INTERRUPT THIS TEST      !!!!!')
        factory.log('!!!!! OTHERWISE YOUR FIRMWARE MAY BE CORRUPTED !!!!!')

        # print os.getcwd()
        for conf in eeprom_sets:
            ## TODO XXX FIXME Verifying EC RW seems hanging system.
            ## We need to fix this later.
            if conf['name'] == 'EC':
                factory.log(' ** Bypassing EC RO TEST ** ')
                continue
            # select target
            if not self.flashrom.select_target(conf['target']):
                raise error.TestError('ERROR: cannot select target %s' %
                        conf['name'])
            # build layout
            original = self.flashrom.read_whole()
            if not original:
                raise error.TestError('Cannot read valid flash rom data.')
            flashrom_size = len(original)
            (layout_map, ro_list, rw_list) = self.build_layout_map(
                    conf['layout'], flashrom_size)
            # ro test
            if self.verbose:
                print ' - RO testing %s: %s' % (conf['name'], ','.join(ro_list))
                factory.log(' - RO testing %s: %s' %
                            (conf['name'], ','.join(ro_list)))
            self.check_write_protection(layout_map, ro_list, False, original)
            # rw test
            if self.verbose:
                print ' - RW testing %s: %s' % (conf['name'], ','.join(rw_list))
                factory.log(' - RW testing %s: %s' %
                            (conf['name'], ','.join(rw_list)))
            self.check_write_protection(layout_map, rw_list, True, original)

        # restore default selection.
        if not self.flashrom.select_target(system_default_selection):
            raise error.TestError('ERROR: cannot restore target.')


if __name__ == "__main__":
    print "please run this program with autotest."
