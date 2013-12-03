# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections, logging, numpy, os, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, cros_ui, cros_ui_test, httpd
from autotest_lib.client.cros import power_rapl, power_status, power_utils
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros import flimflam_test_path
import flimflam

params_dict = {
    'test_time_ms': '_mseconds',
    'should_scroll': '_should_scroll',
    'should_scroll_up': '_should_scroll_up',
    'scroll_loop': '_scroll_loop',
    'scroll_interval_ms': '_scroll_interval_ms',
    'scroll_by_pixels': '_scroll_by_pixels',
    'tasks': '_tasks',
}


class power_LoadTest(cros_ui_test.UITest):
    """test class"""
    version = 2
    _creds = 'power.loadtest@gmail.com:power_LoadTest'


    def start_authserver(self):
        """
        Override cros_ui_test.UITest's start_authserver.
        Do not use auth server and local dns for our test. We need to be
        able to reach the web.
        """
        pass


    def ensure_login_complete(self):
        """
        Override cros_ui_test.UITest's ensure_login_complete.
        Do not use auth server and local dns for our test. We need to be
        able to reach the web.
        """
        pass


    def initialize(self, creds=_creds, percent_initial_charge_min=None,
                 check_network=True, loop_time=3600, loop_count=1,
                 should_scroll='true', should_scroll_up='true',
                 scroll_loop='false', scroll_interval_ms='10000',
                 scroll_by_pixels='600', test_low_batt_p=3,
                 verbose=True, force_wifi=False, wifi_ap='', wifi_sec='none',
                 wifi_pw='', tasks="", kblight_percent=10, volume_level=10,
                 mic_gain=10, low_batt_margin_p=2):
        """
        percent_initial_charge_min: min battery charge at start of test
        check_network: check that Ethernet interface is not running
        loop_count: number of times to loop the test for
        loop_time: length of time to run the test for in each loop
        should_scroll: should the extension scroll pages
        should_scroll_up: should scroll in up direction
        scroll_loop: continue scrolling indefinitely
        scroll_interval_ms: how often to scoll
        scroll_by_pixels: number of pixels to scroll each time
        kblight_percent: percent brightness of keyboard backlight
        volume_level: percent audio volume level
        mic_gain: percent audio microphone gain level
        test_low_batt_p: percent battery at which test should stop
        sys_low_batt_p: percent battery at which power manager will
            shut-down the device
        sys_low_batt_s: seconds battery at which power manager will
            shut-down the device
        low_batt_margin_p: percent low battery margin to be added to
            sys_low_batt_p to guarantee test completes prior to powerd shutdown
        """
        self._backlight = None
        self._services = None
        self._loop_time = loop_time
        self._loop_count = loop_count
        self._mseconds = self._loop_time * 1000
        self._verbose = verbose

        self._sys_low_batt_p = 0.
        self._sys_low_batt_s = 0.
        self._test_low_batt_p = test_low_batt_p
        self._should_scroll = should_scroll
        self._should_scroll_up = should_scroll_up
        self._scroll_loop = scroll_loop
        self._scroll_interval_ms = scroll_interval_ms
        self._scroll_by_pixels = scroll_by_pixels
        self._tmp_keyvals = {}
        self._power_status = power_status.get_status()
        self._force_wifi = force_wifi
        self._testServer = None
        self._tasks = '\'' + tasks.replace(' ','') + '\''
        self._backchannel = None
        self._kblight_percent = kblight_percent
        self._volume_level = volume_level
        self._mic_gain = mic_gain
        self._wait_time = 60
        self._stats = collections.defaultdict(list)

        self._power_status.assert_battery_state(percent_initial_charge_min)
        # If force wifi enabled, convert eth0 to backchannel and connect to the
        # specified WiFi AP.
        if self._force_wifi:
            # If backchannel is already running, don't run it again.
            self._backchannel = backchannel.Backchannel()
            if not self._backchannel.setup():
                raise error.TestError('Could not setup Backchannel network.')

            if not flimflam.FlimFlam().ConnectService(retries=3,
                                                      retry=True,
                                                      service_type='wifi',
                                                      ssid=wifi_ap,
                                                      security=wifi_sec,
                                                      passphrase=wifi_pw,
                                                      mode='managed')[0]:
                raise error.TestError('Could not connect to WiFi network.')
        else:
            # Find all wired ethernet interfaces.
            # TODO: combine this with code in network_DisableInterface, in a
            # common library somewhere.
            ifaces = [ nic.strip() for nic in os.listdir('/sys/class/net/')
                if ((not os.path.exists('/sys/class/net/' + nic + '/phy80211'))
                    and nic.find('eth') != -1) ]
            logging.debug(str(ifaces))
            for iface in ifaces:
                if check_network and \
                        backchannel.is_network_iface_running(iface):
                    raise error.TestError('Ethernet interface is active. ' +
                                          'Please remove Ethernet cable')

        # record the max backlight level
        self._backlight = power_utils.Backlight()
        self._tmp_keyvals['level_backlight_max'] = \
            self._backlight.get_max_level()

        # fix up file perms for the power test extension so that chrome
        # can access it
        os.system('chmod -R 755 %s' % self.bindir)

        # write test parameters to the params.js file to be read by the test
        # extension.
        self._write_ext_params()

        # setup a HTTP Server to listen for status updates from the power
        # test extension
        self._testServer = httpd.HTTPListener(8001, docroot=self.bindir)
        self._testServer.run()

        # initialize various interesting power related stats
        self._statomatic = power_status.StatoMatic()

        self._power_status.refresh()
        (self._sys_low_batt_p, self._sys_low_batt_s) = \
            self._get_sys_low_batt_values()
        min_low_batt_p = min(self._sys_low_batt_p + low_batt_margin_p, 100)
        if self._sys_low_batt_p and (min_low_batt_p > self._test_low_batt_p):
            logging.warn("test low battery threshold is below system " +
                         "low battery requirement.  Setting to %f",
                         min_low_batt_p)
            self._test_low_batt_p = min_low_batt_p

        self._ah_charge_start = self._power_status.battery[0].charge_now
        self._wh_energy_start = self._power_status.battery[0].energy

        super(power_LoadTest, self).initialize(creds=creds)

    def run_once(self):
        import pyauto

        t0 = time.time()
        ext_path = os.path.join(os.path.dirname(__file__), 'extension.crx')

        try:
            kblight = power_utils.KbdBacklight()
            kblight.set(self._kblight_percent)
            self._tmp_keyvals['percent_kbd_backlight'] = kblight.get()
        except power_utils.KbdBacklightException as e:
            logging.info("Assuming no keyboard backlight due to :: %s", str(e))
            kblight = None

        self._services = service_stopper.ServiceStopper(
            service_stopper.ServiceStopper.POWER_DRAW_SERVICES)
        self._services.stop_services()

        measurements = \
            [power_status.SystemPower(self._power_status.battery_path)]
        if power_utils.has_rapl_support():
            measurements += power_rapl.create_rapl()
        self._plog = power_status.PowerLogger(measurements, seconds_period=20)
        self._tlog = power_status.TempLogger([], seconds_period=20)
        self._plog.start()
        self._tlog.start()

        for i in range(self._loop_count):
            start_time = time.time()
            # the power test extension will report its status here
            latch = self._testServer.add_wait_url('/status')

            # Installing the extension will also fire it up.
            ext_id = self.pyauto.InstallExtension(ext_path)

            # reset X settings since X gets restarted upon login
            # TODO(tbroch) This requirement is likely no longer true.  Deprecate
            # after testing.
            self._do_xset()

            # reset backlight level since powerd might've modified it
            # based on ambient light
            self._set_backlight_level()
            self._set_lightbar_level()
            if kblight:
                kblight.set(self._kblight_percent)
            audio_helper.set_volume_levels(self._volume_level,
                                           self._mic_gain)

            low_battery = self._do_wait(self._verbose, self._loop_time,
                                        latch)

            self._plog.checkpoint('loop%d' % (i), start_time)
            self._tlog.checkpoint('loop%d' % (i), start_time)
            if self._verbose:
                logging.debug('loop %d completed', i)

            if low_battery:
                logging.info('Exiting due to low battery')
                break

            try:
                self.pyauto.UninstallExtensionById(ext_id)
            except pyauto.AutomationCommandFail, e:
                # Seems harmles, so treat as non-fatal?
                logging.warn("Error uninstalling extension: %s", str(e))

        t1 = time.time()
        self._tmp_keyvals['minutes_battery_life_tested'] = (t1 - t0) / 60


    def postprocess_iteration(self):
        def _log_stats(prefix, stats):
            if not len(stats):
                return
            np = numpy.array(stats)
            logging.debug("%s samples: %d", prefix, len(np))
            logging.debug("%s mean:    %.2f", prefix, np.mean())
            logging.debug("%s stdev:   %.2f", prefix, np.std())
            logging.debug("%s max:     %.2f", prefix, np.max())
            logging.debug("%s min:     %.2f", prefix, np.min())


        def _log_per_loop_stats():
            samples_per_loop = self._loop_time / self._wait_time + 1
            for kname in self._stats:
                start_idx = 0
                loop = 1
                for end_idx in xrange(samples_per_loop, len(self._stats[kname]),
                                      samples_per_loop):
                    _log_stats("%s loop %d" % (kname, loop),
                               self._stats[kname][start_idx:end_idx])
                    loop += 1
                    start_idx = end_idx


        def _log_all_stats():
            for kname in self._stats:
                _log_stats(kname, self._stats[kname])


        keyvals = self._plog.calc()
        keyvals.update(self._tlog.calc())
        keyvals.update(self._statomatic.publish())

        _log_all_stats()
        _log_per_loop_stats()

        # record battery stats
        keyvals['a_current_now'] = self._power_status.battery[0].current_now
        keyvals['ah_charge_full'] = self._power_status.battery[0].charge_full
        keyvals['ah_charge_full_design'] = \
                             self._power_status.battery[0].charge_full_design
        keyvals['ah_charge_start'] = self._ah_charge_start
        keyvals['ah_charge_now'] = self._power_status.battery[0].charge_now
        keyvals['ah_charge_used'] = keyvals['ah_charge_start'] - \
                                    keyvals['ah_charge_now']
        keyvals['wh_energy_start'] = self._wh_energy_start
        keyvals['wh_energy_now'] = self._power_status.battery[0].energy
        keyvals['wh_energy_used'] = keyvals['wh_energy_start'] - \
                                    keyvals['wh_energy_now']
        keyvals['v_voltage_min_design'] = \
                             self._power_status.battery[0].voltage_min_design
        keyvals['wh_energy_full_design'] = \
                             self._power_status.battery[0].energy_full_design
        keyvals['v_voltage_now'] = self._power_status.battery[0].voltage_now

        keyvals.update(self._tmp_keyvals)

        keyvals['percent_sys_low_battery'] = self._sys_low_batt_p
        keyvals['seconds_sys_low_battery'] = self._sys_low_batt_s
        voltage_np = numpy.array(self._stats['v_voltage_now'])
        voltage_mean = voltage_np.mean()
        keyvals['v_voltage_mean'] = voltage_mean
        bat_life_scale = (keyvals['ah_charge_full_design'] /
                          keyvals['ah_charge_used']) * \
                          ((100 - keyvals['percent_sys_low_battery']) / 100)

        keyvals['minutes_battery_life'] = bat_life_scale * \
            keyvals['minutes_battery_life_tested']
        # In the case where sys_low_batt_s is non-zero subtract those minutes
        # from the final extrapolation.
        if self._sys_low_batt_s:
            keyvals['minutes_battery_life'] -= self._sys_low_batt_s / 60

        keyvals['a_current_rate'] = keyvals['ah_charge_used'] * 60 / \
                                    keyvals['minutes_battery_life_tested']
        keyvals['w_energy_rate'] = keyvals['wh_energy_used'] * 60 / \
                                   keyvals['minutes_battery_life_tested']
        self.write_perf_keyval(keyvals)
        self._plog.save_results(self.resultsdir)
        self._tlog.save_results(self.resultsdir)


    def cleanup(self):
        if self._backlight:
            self._backlight.restore()
        if self._services:
            self._services.restore_services()

        # cleanup backchannel interface
        if self._backchannel:
            self._backchannel.teardown()
        if self._testServer:
            self._testServer.stop()
        super(power_LoadTest, self).cleanup()


    def _write_ext_params(self):
        data = ''
        template = 'var %s = %s;\n'
        for k in params_dict:
            data += template % (k, getattr(self, params_dict[k]))

        filename = os.path.join(self.bindir, 'params.js')
        utils.open_write_close(filename, data)

        logging.debug('filename ' + filename)
        logging.debug(data)


    def _do_wait(self, verbose, seconds, latch):
        latched = False
        low_battery = False
        total_time = seconds + self._wait_time
        elapsed_time = 0

        while elapsed_time < total_time:
            time.sleep(self._wait_time)
            elapsed_time += self._wait_time

            self._power_status.refresh()
            charge_now = self._power_status.battery[0].charge_now
            energy_rate = self._power_status.battery[0].energy_rate
            voltage_now = self._power_status.battery[0].voltage_now
            self._stats['w_energy_rate'].append(energy_rate)
            self._stats['v_voltage_now'].append(voltage_now)
            if verbose:
                logging.debug('ah_charge_now %f', charge_now)
                logging.debug('w_energy_rate %f', energy_rate)
                logging.debug('v_voltage_now %f', voltage_now)

            low_battery = (self._power_status.percent_current_charge() <
                           self._test_low_batt_p)

            latched = latch.is_set()

            if latched or low_battery:
                break

        if latched:
            # record chrome power extension stats
            form_data = self._testServer.get_form_entries()
            logging.debug(form_data)
            for e in form_data:
                key = 'ext_' + e
                if key in self._tmp_keyvals:
                    self._tmp_keyvals[key] += form_data[e]
                else:
                    self._tmp_keyvals[key] = form_data[e]
        else:
            logging.debug("Didn't get status back from power extension")

        return low_battery


    def _do_xset(self):
        XSET = 'LD_LIBRARY_PATH=/usr/local/lib xset'
        # Disable X screen saver
        cros_ui.xsystem('%s s 0 0' % XSET)
        # Disable DPMS Standby/Suspend/Off
        cros_ui.xsystem('%s dpms 0 0 0' % XSET)
        # Force monitor on
        cros_ui.xsystem('%s dpms force on' % XSET)
        # Save off X settings
        cros_ui.xsystem('%s q' % XSET)


    def _set_backlight_level(self):
        self._backlight.set_default()
        # record brightness level
        self._tmp_keyvals['level_backlight_current'] = \
            self._backlight.get_level()


    def _set_lightbar_level(self, level='off'):
        """Set lightbar level.

        Args:
          level: string value to set lightbar to.  See ectool for more details.
        """
        rv = utils.system('which ectool', ignore_status=True)
        if rv:
            return
        rv = utils.system('ectool lightbar %s' % level, ignore_status=True)
        if rv:
            logging.info('Assuming no lightbar due to non-zero exit status')
        else:
            logging.info('Setting lightbar to %s', level)
            self._tmp_keyvals['level_lightbar_current'] = level


    def _get_sys_low_batt_values(self):
        """Determine the low battery values for device and return.

        2012/11/01: power manager (powerd.cc) parses parameters in filesystem
          and outputs a log message like:

           [1101/173837:INFO:powerd.cc(258)] Using low battery time threshold
                     of 0 secs and using low battery percent threshold of 3.5

           It currently checks to make sure that only one of these values is
           defined.

        Returns:
          Tuple of (percent, seconds)
            percent: float of low battery percentage
            seconds: float of low battery seconds

        """
        split_re = 'threshold of'

        powerd_log = '/var/log/power_manager/powerd.LATEST'
        cmd = 'grep "low battery time" %s' % powerd_log
        line = utils.system_output(cmd)
        secs = float(line.split(split_re)[1].split()[0])
        percent = float(line.split(split_re)[2].split()[0])
        if secs and percent:
            raise error.TestError("Low battery percent and seconds " +
                                  "are non-zero.")
        return (percent, secs)
