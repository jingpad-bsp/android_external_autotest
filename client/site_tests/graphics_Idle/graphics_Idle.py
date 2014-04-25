# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_logging
from autotest_lib.client.common_lib.cros import chrome


class graphics_Idle(test.test):
    """Class for graphics_Idle.  See 'control' for details."""
    version = 1


    def run_once(self):
        # We use kiosk mode to make sure Chrome is idle.
        with chrome.Chrome(logged_in=False, extra_browser_args=['--kiosk']):
            self._gpu_type = utils.get_gpu_family()
            errors = ''
            errors += self.verify_lvds_downclock()
            errors += self.verify_short_blanking()
            errors += self.verify_graphics_rc6()
            errors += self.verify_graphics_dvfs()
            errors += self.verify_graphics_fbc()
            errors += self.verify_graphics_gem_idle()
            if errors:
                raise error.TestFail(errors)


    def verify_lvds_downclock(self):
        """On systems which support LVDS downclock, checks the kernel log for
        a message that an LVDS downclock mode has been added."""
        logging.info('Running verify_lvds_downclock')
        board = utils.get_board()
        if not (board == 'alex' or board == 'lumpy' or
                board == 'parrot' or board == 'parrot_ivb' or
                board == 'stout'):
            return ''

        # Get the downclock message from the logs.
        reader = cros_logging.LogReader()
        reader.set_start_by_reboot(-1)
        if not reader.can_find('Adding LVDS downclock mode'):
            logging.error('Error: LVDS downclock quirk not applied.')
            return 'LVDS downclock quirk not applied. '

        return ''


    def verify_short_blanking(self):
        """On some baytrail systems, checks the kernel log for a message that a
        short blanking mode has been added."""
        logging.info('Running verify_short_blanking')
        board = utils.get_board()
        # TODO(marcheu): add more BYT machines
        if (board != 'rambi' and board != 'squawks'):
            return ''

        # Get the downclock message from the logs.
        reader = cros_logging.LogReader()
        reader.set_start_by_reboot(-1)
        if not reader.can_find('Modified preferred into a short blanking mode'):
            logging.error('Error: short blanking not added.')
            return 'Short blanking not added. '

        return ''


    def verify_graphics_rc6(self):
        """ On systems which support RC6 (non atom), check that we are able to
        get into rc6; idle before doing so, and retry every second for 20
        seconds."""
        logging.info('Running verify_graphics_rc6')
        if (self._gpu_type == 'haswell' or self._gpu_type == 'ivybridge' or
            self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while found == False and tries < 20:
                time.sleep(1)
                param_path = '/sys/kernel/debug/dri/0/i915_drpc_info'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                drpc_info_file = open (param_path, "r")
                for line in drpc_info_file:
                    match = re.search(r'Current RC state: (.*)', line)
                    if match:
                        found = match.group(1) != 'on'
                        break

                tries += 1
                drpc_info_file.close()

            if not found:
                logging.error('Error: did not see the GPU in RC6.')
                return 'Did not see the GPU in RC6. '

        return ''


    def verify_graphics_dvfs(self):
        """ On systems which support DVFS, check that we get into the lowest
        clock frequency; idle before doing so, and retry every second for 20
        seconds."""
        logging.info('Running verify_graphics_dvfs')
        if self._gpu_type == 'mali':
            tries = 0
            found = False
            while found == False and tries < 20:
                time.sleep(1)
                param_path = '/sys/devices/11800000.mali/clock'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                clock = utils.read_file(param_path)
                if int(clock) <= 266000000:
                    found = 1
                    break

                tries += 1

            if not found:
                logging.error('Error: did not see the min DVFS clock')
                return 'Did not see the min DVFS clock. '

        return ''


    def verify_graphics_fbc(self):
        """ On systems which support FBC, check that we can get into FBC;
        idle before doing so, and retry every second for 20 seconds."""
        logging.info('Running verify_graphics_fbc')

        # Link's FBC is disabled (crbug.com/338588).
        # TODO(marcheu): remove this when/if we fix this bug.
        board = utils.get_board()
        if board == 'link':
            return ''

        if (self._gpu_type == 'haswell' or self._gpu_type == 'ivybridge' or
            self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while found == False and tries < 20:
                time.sleep(1)
                # Kernel 3.4 has i915_fbc, kernel 3.8+ has i915_fbc_status,
                # so we check for both.
                param_path = '/sys/kernel/debug/dri/0/i915_fbc_status'
                if not os.path.exists(param_path):
                    param_path = '/sys/kernel/debug/dri/0/i915_fbc'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                fbc_info_file = open (param_path, "r")
                for line in fbc_info_file:
                    match = re.search('FBC enabled', line)
                    if match:
                        found = 1
                        break

                tries += 1
                fbc_info_file.close()

            if not found:
                logging.error('Error: did not see FBC enabled.')
                return 'Did not see FBC enabled. '


        return ''


    def verify_graphics_gem_idle(self):
        """ On systems which have i915, check that we can get all gem objects
        to become idle (i.e. the i915_gem_active list need to go to 0);
        idle before doing so, and retry every second for 20 seconds."""
        logging.info('Running verify_graphics_gem_idle')
        if (self._gpu_type == 'baytrail' or self._gpu_type == 'haswell' or
            self._gpu_type == 'ivybridge' or self._gpu_type == 'pinetrail' or
            self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while found == False and tries < 20:
                time.sleep(1)
                gem_path = '/sys/kernel/debug/dri/0/i915_gem_active'
                if not os.path.exists(gem_path):
                    logging.error('Error: %s not found.', gem_path)
                    break
                gem_file = open(gem_path, "r")
                for line in gem_file:
                    found = re.search('Total 0 objects', line)
                    if found:
                        break

                tries += 1
                gem_file.close()

            if not found:
                logging.error('Error: did not reach 0 gem actives.')
                return 'Did not reach 0 gem actives. '

        return ''


