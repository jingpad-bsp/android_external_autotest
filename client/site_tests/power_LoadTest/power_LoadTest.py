# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_httpd, \
                            site_power_status, site_ui, utils

params_dict = {
    'test_time_ms': '_mseconds',
    'should_scroll': '_should_scroll',
    'should_scroll_up': '_should_scroll_up',
    'scroll_loop': '_scroll_loop',
    'scroll_interval_ms': '_scroll_interval_ms',
    'scroll_by_pixels': '_scroll_by_pixels',
}

form_entries = ['status', 'succeeded', 'failed']

class power_LoadTest(test.test):
    version = 1

    def setup(self):
        # TODO(snanda): Remove once power manager is in
        shutil.copy(os.path.join(os.environ['SYSROOT'], 'usr/bin/xset'),
                                 self.bindir)
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)


    def initialize(self, percent_initial_charge_min=None, check_network=True,
                   seconds=3600, should_scroll='true', should_scroll_up='true',
                   scroll_loop='false', scroll_interval_ms='10000',
                   scroll_by_pixels='600', verbose=True):
        """
        percent_initial_charge_min: min battery charge at start of test
        check_network: check that Ethernet interface is not running
        seconds: length of time to run test for
        should_scroll: should the extension scroll pages
        should_scroll_up: should scroll in up direction
        scroll_loop: continue scrolling indefinitely
        scroll_interval_ms: how often to scoll
        scroll_by_pixels: number of pixels to scroll each time
        """

        self._seconds = seconds
        self._mseconds = seconds * 1000
        self._verbose = verbose
        self._should_scroll = should_scroll
        self._should_scroll_up = should_scroll_up
        self._scroll_loop = scroll_loop
        self._scroll_interval_ms = scroll_interval_ms
        self._scroll_by_pixels = scroll_by_pixels
        self._form_data = {}

        self._power_status = site_power_status.get_status()

        # verify that initial conditions are met:
        if self._power_status.linepower[0].online:
            raise error.TestNAError(
                'Running on AC power. Please remove AC power cable')

        percent_initial_charge = self._percent_current_charge()
        if percent_initial_charge_min and percent_initial_charge < \
                                          percent_initial_charge_min:
            raise error.TestError('Initial charge (%f) less than min (%f)'
                      % (percent_initial_charge, percent_initial_charge_min))

        if check_network and self._is_network_iface_running('eth0'):
            raise error.TestNAError(
                'Ethernet interface is active. Please remove Ethernet cable')

        # TODO (snanda):
        # - set brightness level
        # - turn off suspend on idle (not implemented yet in Chrome OS)

        # disable screen locker
        os.system('stop screen-locker')

        # disable screen blanking
        site_ui.xsystem(os.path.join(self.bindir, 'xset') + ' -dpms')

        # fix up file perms for the power test extension so that chrome
        # can access it
        os.system('chmod -R 755 %s' % self.bindir)

        # write test parameters to the power extension's params.js file
        self._ext_path = os.path.join(self.bindir, 'extension')
        self._write_ext_params()

        # setup a HTTP Server to listen for status updates from the power
        # test extension
        self._testServer = site_httpd.HTTPListener(8001, docroot=self.bindir)
        self._testServer.run()

        # initialize various interesting power related stats
        self._usb_stats = site_power_status.USBSuspendStats()
        self._cpufreq_stats = site_power_status.CPUFreqStats()
        self._cpuidle_stats = site_power_status.CPUIdleStats()


    def run_once(self):
        self._reset_form_entries()

        self._usb_stats.refresh()
        self._cpufreq_stats.refresh()
        self._cpuidle_stats.refresh()

        self._power_status.refresh()
        self._ah_charge_start = self._power_status.battery[0].charge_now
        self._wh_energy_start = self._power_status.battery[0].energy

        # the power test extension will report its status here
        latch = self._testServer.add_wait_url('/status')

        # launch chrome with power test extension
        args = '--load-extension=%s' % self._ext_path
        session = site_ui.ChromeSession(args, clean_state=False)

        self._do_wait(self._verbose, self._seconds, latch, session)


    def postprocess_iteration(self):
        keyvals = {}

        # refresh power related statistics
        usb_stats = self._usb_stats.refresh()
        cpufreq_stats = self._cpufreq_stats.refresh()
        cpuidle_stats = self._cpuidle_stats.refresh()

        # record percent time USB devices were not in suspended state
        keyvals['percent_usb_active'] = usb_stats

        # record percent time spent in each CPU C-state
        for state in cpuidle_stats:
            keyvals['percent_cpuidle_%s_time' % state] = cpuidle_stats[state]

        # record percent time spent at each CPU frequency
        for freq in cpufreq_stats:
            keyvals['percent_cpufreq_%s_time' % freq] = cpufreq_stats[freq]

        # record battery stats
        keyvals['a_current_now'] = self._power_status.battery[0].current_now
        keyvals['ah_charge_full'] = self._power_status.battery[0].charge_full
        keyvals['ah_charge_full_design'] = \
                             self._power_status.battery[0].charge_full_design
        keyvals['ah_charge_start'] = self._ah_charge_start
        keyvals['ah_charge_now'] = self._power_status.battery[0].charge_now
        keyvals['ah_charge_used'] = keyvals['ah_charge_start'] - \
                                    keyvals['ah_charge_now']
        keyvals['w_energy_rate'] = self._power_status.battery[0].energy_rate
        keyvals['wh_energy_start'] = self._wh_energy_start
        keyvals['wh_energy_now'] = self._power_status.battery[0].energy
        keyvals['wh_energy_used'] = keyvals['wh_energy_start'] - \
                                    keyvals['wh_energy_now']
        keyvals['v_voltage_min_design'] = \
                             self._power_status.battery[0].voltage_min_design
        keyvals['v_voltage_now'] = self._power_status.battery[0].voltage_now

        # record chrome power extension stats
        for e in self._form_data:
            keyvals['ext_' + e] = self._form_data[e]

        self.write_perf_keyval(keyvals)


    def cleanup(self):
        # re-enable screen blanking
        site_ui.xsystem(os.path.join(self.bindir, 'xset') + ' +dpms')

        # re-enable screen locker
        os.system('start screen-locker')


    def _is_network_iface_running(self, name):
        try:
            out = utils.system_output('ifconfig %s' % name)
        except error.CmdError, e:
            logging.info(e)
            return False

        match = re.search('RUNNING', out, re.S)
        return match


    def _percent_current_charge(self):
        return self._power_status.battery[0].charge_now * 100 / \
               self._power_status.battery[0].charge_full_design


    def _write_ext_params(self):
        data = ''
        template= 'var %s = %s;\n'
        for k in params_dict:
            data += template % (k, getattr(self, params_dict[k]))

        filename = os.path.join(self._ext_path, 'params.js')
        utils.open_write_close(filename, data)

        logging.debug('filename ' + filename)
        logging.debug(data)


    def _reset_form_entries(self):
        self._form_data = {}


    def _do_wait(self, verbose, seconds, latch, session):
        latched = False
        total_time = seconds + 120
        elapsed_time = 0

        wait_time = total_time
        if verbose:
            wait_time = 60

        while elapsed_time < total_time:
            time.sleep(wait_time)
            elapsed_time += wait_time

            self._power_status.refresh()
            logging.debug('ah_charge_now %f' \
                % self._power_status.battery[0].charge_now)
            logging.debug('w_energy_rate %f' \
                % self._power_status.battery[0].energy_rate)

            if latch.is_set():
                latched = True
                self._form_data = self._testServer.get_form_entries()
                logging.debug(self._form_data)
                break

        if not latched:
            logging.debug("Didn't get status back from power extension")

        session.close()
