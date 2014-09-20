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
        # Try to protect against runaway previous tests.
        if not utils.wait_for_idle_cpu(60.0, 0.1):
            raise error.TestFail('Could not get idle CPU.')
        # We use kiosk mode to make sure Chrome is idle.
        with chrome.Chrome(logged_in=False, extra_browser_args=['--kiosk']):
            self._gpu_type = utils.get_gpu_family()
            errors = ''
            errors += self.verify_graphics_dvfs()
            errors += self.verify_graphics_fbc()
            errors += self.verify_graphics_gem_idle()
            errors += self.verify_graphics_i915_min_clock()
            errors += self.verify_graphics_rc6()
            errors += self.verify_lvds_downclock()
            errors += self.verify_short_blanking()
            if errors:
                raise error.TestFail(errors)


    def verify_lvds_downclock(self):
        """On systems which support LVDS downclock, checks the kernel log for
        a message that an LVDS downclock mode has been added."""
        logging.info('Running verify_lvds_downclock')
        board = utils.get_board()
        if not (board == 'alex' or board == 'lumpy' or
                board == 'parrot' or board == 'stout'):
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
        if (board != 'rambi'):
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
        if (self._gpu_type == 'broadwell' or self._gpu_type == 'haswell' or
            self._gpu_type == 'ivybridge' or self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while found == False and tries < 20:
                time.sleep(1)
                param_path = '/sys/kernel/debug/dri/0/i915_drpc_info'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                with open (param_path, 'r') as drpc_info_file:
                    for line in drpc_info_file:
                        match = re.search(r'Current RC state: (.*)', line)
                        if match and match.group(1) != 'on':
                            found = True
                            break

                tries += 1

            if not found:
                utils.log_process_activity()
                logging.error('Error: did not see the GPU in RC6.')
                return 'Did not see the GPU in RC6. '

        return ''


    def verify_graphics_i915_min_clock(self):
        """ On i915 systems, check that we get into the lowest clock frequency;
        idle before doing so, and retry every second for 20 seconds."""
        logging.info('Running verify_graphics_i915_min_clock')
        if (self._gpu_type == 'baytrail' or self._gpu_type == 'haswell' or
            self._gpu_type == 'ivybridge' or self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while not found and tries < 80:
                time.sleep(0.25)
                param_path = '/sys/kernel/debug/dri/0/i915_cur_delayinfo'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break

                with open (param_path, 'r') as delayinfo_file:
                    for line in delayinfo_file:
                        # This file has a different format depending on the board,
                        # so we parse both. Also, it would be tedious to add the
                        # minimum clock for each board, so instead we use 650MHz
                        # which is the max of the minimum clocks.
                        match = re.search(r'CAGF: (.*)MHz', line)
                        if match and int(match.group(1)) <= 650:
                            found = True
                            break

                        match = re.search(r'current GPU freq: (.*) MHz', line)
                        if match and int(match.group(1)) <= 650:
                            found = True
                            break

                tries += 1

            if not found:
                utils.log_process_activity()
                logging.error('Error: did not see the min i915 clock')
                return 'Did not see the min i915 clock. '

        return ''


    def verify_graphics_dvfs(self):
        """ On systems which support DVFS, check that we get into the lowest
        clock frequency; idle before doing so, and retry every second for 20
        seconds."""
        logging.info('Running verify_graphics_dvfs')
        if self._gpu_type == 'mali':
            tries = 0
            found = False
            while not found and tries < 80:
                time.sleep(0.25)
                param_path = '/sys/devices/11800000.mali/clock'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                clock = utils.read_file(param_path)
                if int(clock) <= 266000000:
                    found = True
                    break

                tries += 1

            if not found:
                utils.log_process_activity()
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

        # Machines which don't have a monitor can't get FBC.
        if utils.has_no_monitor():
            return ''

        if (self._gpu_type == 'haswell' or self._gpu_type == 'ivybridge' or
            self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while not found and tries < 20:
                time.sleep(1)
                # Kernel 3.4 has i915_fbc, kernel 3.8+ has i915_fbc_status,
                # so we check for both.
                param_path = '/sys/kernel/debug/dri/0/i915_fbc_status'
                if not os.path.exists(param_path):
                    param_path = '/sys/kernel/debug/dri/0/i915_fbc'
                if not os.path.exists(param_path):
                    logging.error('Error: %s not found.', param_path)
                    break
                with open (param_path, 'r') as fbc_info_file:
                    for line in fbc_info_file:
                        if re.search('FBC enabled', line):
                            found = True
                            break

                tries += 1

            if not found:
                logging.error('Error: did not see FBC enabled.')
                return 'Did not see FBC enabled. '


        return ''


    def verify_graphics_gem_idle(self):
        """ On systems which have i915, check that we can get all gem objects
        to become idle (i.e. the i915_gem_active list need to go to 0);
        idle before doing so, and retry every second for 20 seconds."""
        logging.info('Running verify_graphics_gem_idle')
        if (self._gpu_type == 'baytrail' or self._gpu_type == 'broadwell' or
            self._gpu_type == 'haswell' or self._gpu_type == 'ivybridge' or
            self._gpu_type == 'pinetrail' or self._gpu_type == 'sandybridge'):
            tries = 0
            found = False
            while not found and tries < 240:
                time.sleep(0.25)
                gem_path = '/sys/kernel/debug/dri/0/i915_gem_active'
                if not os.path.exists(gem_path):
                    logging.error('Error: %s not found.', gem_path)
                    break
                with open (gem_path, 'r') as gem_file:
                    for line in gem_file:
                        if re.search('Total 0 objects', line):
                            found = True
                            break

                tries += 1

            if not found:
                utils.log_process_activity()
                logging.error('Error: did not reach 0 gem actives.')
                return 'Did not reach 0 gem actives. '

        return ''


