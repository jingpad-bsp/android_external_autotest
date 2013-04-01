# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
import urllib
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros import cros_ui, cros_ui_test
from autotest_lib.client.cros import flimflam_test_path
from autotest_lib.client.cros import httpd
from autotest_lib.client.cros import power_rapl, power_status, power_utils
from autotest_lib.client.cros import service_stopper
import flimflam  # Requires flimflam_test_path to be imported first.


class power_Consumption(cros_ui_test.UITest):
    """Measure power consumption for different types of loads.

    This test runs a series of different tasks like media playback, flash
    animation, large file download etc. It measures and reports power
    consumptions during each of those tasks.
    """

    version = 1


    def start_authserver(self):
        """ For some reason if we fire up the authserver, we get stuck at
        the network selection dialog.
        """
        pass


    def initialize(self, creds='$default'):
        super(power_Consumption, self).initialize(creds=creds)
        self._backlight = None
        self._services = None

        # Some things from pyauto module are not accessible from
        # self.pyauto object
        import pyauto
        self._pyauto_module = pyauto

        # Time to exclude from calculation after firing a task [seconds]
        self._stabilization_seconds = 5
        self._power_status = power_status.get_status()
        # Verify that we are running on battery and the battery is
        # sufficiently charged
        self._power_status.assert_battery_state(30)

        # Find the battery capacity to report expected battery life in hours
        batinfo = self._power_status.battery[0]
        self.energy_full_design = batinfo.energy_full_design
        logging.info("energy_full_design = %0.3f Wh", self.energy_full_design)

        self._do_xset()

        # Local data and web server settings. Tarballs with traditional names
        # like *.tgz don't get copied to the image by ebuilds (see
        # AUTOTEST_FILE_MASK in autotest-chrome ebuild).
        self._static_sub_dir = 'static_sites'
        utils.extract_tarball_to_dir(
                'static_sites.tgz.keep',
                os.path.join(self.bindir, self._static_sub_dir))
        self._media_dir = '/home/chronos/user/Downloads/'
        self._httpd_port = 8000
        self._url_base = 'http://localhost:%s/' % self._httpd_port
        self._test_server = httpd.HTTPListener(self._httpd_port,
                                               docroot=self.bindir)

        self._test_server.run()


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


    def _download_test_data(self):
        """Download audio and video files.

        This is also used as payload for download test.
        """

        repo = 'http://commondatastorage.googleapis.com/chromeos-test-public/'
        file_list = [repo + 'big_buck_bunny/big_buck_bunny_trailer_400p.mp4',]
        if not self.short:
            file_list += [
                repo + 'big_buck_bunny/big_buck_bunny_trailer_400p.ogg',
                repo + 'big_buck_bunny/big_buck_bunny_trailer_1080p.mp4',
                repo + 'big_buck_bunny/big_buck_bunny_trailer_400p.webm',
                repo + 'big_buck_bunny/big_buck_bunny_trailer_1080p.ogg',
                repo + 'big_buck_bunny/big_buck_bunny_trailer_1080p.webm',
                repo + 'wikimedia/Greensleeves.ogg',]

        for url in file_list:
            logging.info('Downloading %s', url)
            utils.unmap_url('', url, self._media_dir)


    def _toggle_fullscreen(self, expected = None):
        """Toggle full screen mode.

        Args:
            expected: boolean, True = full screen, False = normal mode. Will
                raise error.TestError if the actual result is different.
        Returns:
            True if the final state is full screen, False if normal mode.
        Raises:
            error.TestError if |expected| is not None and different from the
            final state.
        """

        self.pyauto.ApplyAccelerator(self._pyauto_module.IDC_FULLSCREEN)
        is_fullscreen = self.pyauto.GetBrowserInfo()['windows'][0]['fullscreen']
        if expected is not None and expected != is_fullscreen:
            raise error.TestError('_toggle_fullscreen() expected %s, got %s' %
                (expected, is_fullscreen))
        return is_fullscreen


    # Below are a series of generic sub-test runners. They run a given task
    # and record the task name and start-end timestamps for future computation
    # of power consumption during the task.
    def _run_func(self, name, func, repeat=1, save_checkpoint=True):
        """Run a given python function as a sub-test."""
        start_time = time.time() + self._stabilization_seconds
        for _ in xrange(repeat):
            ret = func()
        if save_checkpoint:
            self._plog.checkpoint(name, start_time)
        return ret


    def _run_sleep(self, name, seconds=60):
        """Just sleep and record it as a named sub-test"""
        start_time = time.time() + self._stabilization_seconds
        time.sleep(seconds)
        self._plog.checkpoint(name, start_time)


    def _run_cmd(self, name, cmd, repeat=1):
        """Run command in a shell as a sub-test"""
        start_time = time.time() + self._stabilization_seconds
        for _ in xrange(repeat):
            exit_status = utils.system(cmd, ignore_status=True)
            if exit_status != 0:
                logging.error('run_cmd: the following command terminated with'
                                'a non zero exit status: %s', cmd)
        self._plog.checkpoint(name, start_time)
        return exit_status


    def _run_until(self, name, predicate, retval=True):
        """Probe the |predicate| function  and wait until it returns true.
        Record the waiting time as a sub-test
        """
        start_time = time.time() + self._stabilization_seconds
        self.pyauto.WaitUntil(predicate, expect_retval=retval)
        self._plog.checkpoint(name, start_time)


    def _run_url(self, name, url, duration):
        """Navigate to URL, sleep for some time and record it as a sub-test."""
        self.pyauto.NavigateToURL(url)
        self._run_sleep(name, duration)
        tab_title = self.pyauto.GetActiveTabTitle()
        logging.info('Sub-test name: %s Tab title: %s.', name, tab_title)


    def _run_url_bg(self, name, url, duration):
        """Run a web site in background tab.

        Navigate to the given URL, open an empty tab to put the one with the
        URL in background, then sleep and record it as a sub-test.

        Args:
            name: sub-test name.
            url: url to open in background tab.
            duration: number of seconds to sleep while taking measurements.
        """
        self.pyauto.NavigateToURL(url)
        # Let it load and settle
        time.sleep(self._stabilization_seconds / 2.)
        tab_title = self.pyauto.GetActiveTabTitle()
        logging.info('App name: %s Tab title: %s.', name, tab_title)
        self.pyauto.AppendTab('about:blank')
        self._run_sleep(name, duration)
        self.pyauto.CloseTab(tab_index=1, windex=0)


    def _run_group_download(self):
        """Download over ethernet. Using video test data as payload."""

        # For short run, the payload is too small to take measurement
        self._run_func('download_eth',
                       self._download_test_data ,
                       repeat=self._repeats,
                       save_checkpoint=not(self.short))


    def _run_group_webpages(self):
        """Runs a series of web pages as sub-tests."""
        data_url = self._url_base + self._static_sub_dir + '/'

        # URLs to be only tested in foreground tab
        urls = [('AboutBlank', 'about:blank')]
        # URLs to be tested in both, background and foreground modes.
        bg_urls = []

        more_urls = [('BallsDHTML',
                      data_url + 'balls/DHTMLBalls/dhtml.htm'),
                     ('BallsFlex',
                      data_url + 'balls/FlexBalls/flexballs.html'),]

        if self.short:
            urls += more_urls
        else:
            bg_urls += more_urls
            bg_urls += [('Parapluesch',
                         'http://www.parapluesch.de/whiskystore/test.htm'),
                         ('PosterCircle',
                          'http://www.webkit.org'
                          '/blog-files/3d-transforms/poster-circle.html'),]

        for name, url in urls + bg_urls:
            self._run_url(name, url, duration=self._duration_secs)

        for name, url in bg_urls:
            self._run_url_bg('bg_' + name, url, duration=self._duration_secs)


    def _run_group_v8(self):
        """Run the V8 benchmark suite as a sub-test.

        Fire it up and wait until it displays "Score".
        """

        url = 'http://v8.googlecode.com/svn/data/benchmarks/v7/run.html'

        js = """s = document.getElementById('status').textContent.substr(0,5);
                window.domAutomationController.send(s);"""

        def v8_func():
            self.pyauto.NavigateToURL(url)
            self.pyauto.WaitUntil(lambda: self.pyauto.ExecuteJavascript(js),
                              expect_retval='Score')

        self._run_func('V8', v8_func, repeat=self._repeats)

        # Write v8 score to log
        js_get_score = """s = document.getElementById('status').textContent;
                window.domAutomationController.send(s);"""
        score = self.pyauto.ExecuteJavascript(js_get_score)
        score = score.strip().split()[1]
        logging.info('V8 Score: %s', score )


    def _run_group_video(self):
        """Run video and audio playback in the browser."""

        # Note: for perf keyvals, key names are defined as VARCHAR(30) in the
        # results DB. Chars above 30 are truncated when saved to DB.
        urls = [('vid400p_h264', 'big_buck_bunny_trailer_400p.mp4'),]
        fullscreen_urls = []
        bg_urls = []

        if not self.short:
            urls += [
                ('vid400p_ogg', 'big_buck_bunny_trailer_400p.ogg'),
                ('vid1080_h264','big_buck_bunny_trailer_1080p.mp4'),
                ('vid400p_vp8', 'big_buck_bunny_trailer_400p.webm'),
                ('vid1080_ogg','big_buck_bunny_trailer_1080p.ogg'),
                ('vid1080_vp8','big_buck_bunny_trailer_1080p.webm'),
                ('audio', 'Greensleeves.ogg'),
                ]

            fullscreen_urls += [
                ('vid1080_h264_fs',
                 'big_buck_bunny_trailer_1080p.mp4'),
                ('vid1080_vp8_fs',
                 'big_buck_bunny_trailer_1080p.webm'),
                ]

            bg_urls += [
                ('bg_vid400p', 'big_buck_bunny_trailer_400p.webm'),
                ]

        # The video files are run from a file:// url. In order to work properly
        # from an http:// url, some careful web server configuration is needed
        def full_url(filename):
            """Create a file:// url for the media file and verify it exists."""
            p = os.path.join(self._media_dir, filename)
            if not os.path.isfile(p):
                raise error.TestError('Media file %s is missing.', p)
            return 'file://' + p

        js_loop_enable = """ve = document.getElementsByTagName('video')[0];
                         ve.loop = true;
                         ve.play();
                         window.domAutomationController.send('');
                         """

        for name, url in urls:
            self.pyauto.NavigateToURL(full_url(url))
            self.pyauto.ExecuteJavascript(js_loop_enable)
            self._run_sleep(name, self._duration_secs)

        for name, url in fullscreen_urls:
            self._toggle_fullscreen(expected=True)
            self.pyauto.NavigateToURL(full_url(url))
            self.pyauto.ExecuteJavascript(js_loop_enable)
            self._run_sleep(name, self._duration_secs)
            self._toggle_fullscreen(expected=False)

        for name, url in bg_urls:
            self.pyauto.NavigateToURL(full_url(url))
            self.pyauto.ExecuteJavascript(js_loop_enable)
            self.pyauto.AppendTab('about:blank')
            self._run_sleep(name, self._duration_secs)
            self.pyauto.CloseTab(tab_index=1, windex=0)


    def _run_group_sound(self):
        """Run non-UI sound test using 'speaker-test'."""

        cmd = 'speaker-test -l %s -t sine -c 2' % (self._repeats * 6)
        self._run_cmd('speaker_test', cmd)


    def _run_group_lowlevel(self):
        """Low level system stuff"""
        mb = min(1024, 32 * self._repeats)
        self._run_cmd('memtester', '/usr/local/sbin/memtester %s 1' % mb)

        # one rep of dd takes about 15 seconds
        root_dev = utils.system_output('rootdev -s').strip()
        cmd = 'dd if=%s of=/dev/null' % root_dev
        self._run_cmd('dd', cmd, repeat=2*self._repeats)


    def _run_group_backchannel(self):
        """WiFi sub-tests."""

        wifi_ap = 'GoogleGuest'
        wifi_sec = 'none'
        wifi_pw = ''

        flim = flimflam.FlimFlam()
        conn = flim.ConnectService(retries=3,
                              retry=True,
                              service_type='wifi',
                              ssid=wifi_ap,
                              security=wifi_sec,
                              passphrase=wifi_pw,
                              mode='managed')
        if not conn[0]:
            logging.error("Could not connect to WiFi")
            return

        logging.info('Starting Backchannel')
        with backchannel.Backchannel():
            # Wifi needs some time to recover after backchanel is activated
            # TODO (kamrik) remove this sleep, once backchannel handles this
            time.sleep(15)

            cmd = 'ping -c %s www.google.com' % (self._duration_secs)
            self._run_cmd('ping_wifi', cmd)

            # This URL must be visible from WiFi network used for test
            big_file_url = ('http://googleappengine.googlecode.com'
                            '/files/GoogleAppEngine-1.6.2.msi')
            cmd = 'curl %s > /dev/null' % big_file_url
            self._run_cmd('download_wifi', cmd, repeat=self._repeats)


    def _run_group_backlight(self):
        """Vary backlight brightness and record power at each setting."""
        for i in [100, 50, 0]:
            self._backlight.set_percent(i)
            start_time = time.time() + self._stabilization_seconds
            time.sleep(30 * self._repeats)
            self._plog.checkpoint('backlight_%03d' % i, start_time)
        self._backlight.set_default()


    def _web_echo(self, msg):
        """ Displays a message in the browser."""
        url = self._url_base + 'echo.html?'
        url += urllib.quote(msg)
        self.pyauto.NavigateToURL(url)


    def _run_test_groups(self, groups):
        """ Run all the test groups.

        Args:
            groups: list of sub-test groups to run. Each sub-test group refers
                to a _run_group_...() function.
        """

        for group in groups:
            logging.info('Running group %s', group)
            # The _web_echo here is important for some tests (esp. non UI)
            # it gets the previous web page replaced with an almost empty one.
            self._web_echo('Running test %s' % group)
            test_func = getattr(self, '_run_group_%s' % group)
            test_func()


    def run_once(self, short=False, test_groups=None, reps=1):
        # Some sub-tests have duration specified directly, _base_secs * reps
        # is used in this case. Others complete whenever the underlying task
        # completes, those are manually tuned to be roughly around
        # reps * 30 seconds. Don't change _base_secs unless you also
        # change the manual tuning in sub-tests
        self._base_secs = 30
        self._repeats = reps
        self._duration_secs = self._base_secs * reps

        # Lists of default tests to run
        UI_TESTS = ['backlight', 'download', 'webpages', 'video', 'v8']
        NONUI_TESTS = ['backchannel', 'sound', 'lowlevel']
        DEFAULT_TESTS = UI_TESTS + NONUI_TESTS
        DEFAULT_SHORT_TESTS = ['download', 'webpages', 'video']

        self.short = short
        if test_groups is None:
            if self.short:
                test_groups = DEFAULT_SHORT_TESTS
            else:
                test_groups = DEFAULT_TESTS

        # Let the login complete
        time.sleep(5)

        self._services = service_stopper.ServiceStopper(
            service_stopper.ServiceStopper.POWER_DRAW_SERVICES)
        self._services.stop_services()

        self._backlight = power_utils.Backlight()
        self._backlight.set_default()

        measurements = \
            [power_status.SystemPower(self._power_status.battery_path)]
        if power_utils.has_rapl_support():
            measurements += power_rapl.create_rapl()
        self._plog = power_status.PowerLogger(measurements)
        self._plog.start()

        # Check that we have a functioning browser and network
        self.pyauto.NavigateToURL('http://www.google.com/')
        if self.pyauto.GetActiveTabTitle() != 'Google':
            raise error.TestError('Could not load www.google.com')

        # Video test must have the data from download test
        if ('video' in test_groups):
            iv = test_groups.index('video')
            if 'download' not in test_groups[:iv]:
                msg = '"download" test must run before "video".'
                raise error.TestError(msg)

        # Run all the test groups
        self._run_test_groups(test_groups)

        # Wrap up
        keyvals = self._plog.calc()

        # Calculate expected battery life time with AboutBlank power draw
        idle_name = 'AboutBlank_system_pwr'
        if idle_name in keyvals:
            hours_life = self.energy_full_design / keyvals[idle_name]
            keyvals['hours_battery_AboutBlank'] = hours_life

        # Calculate a weighted power draw and battery life time. The weights
        # are intended to represent "typical" usage. Some video, some Flash ...
        # and most of the time idle.
        # see http://www.chromium.org/chromium-os/testing/power-testing
        weights = {'vid400p_h264_system_pwr':0.1,
                   'BallsFlex_system_pwr':0.1,
                   'BallsDHTML_system_pwr':0.2,}
        weights[idle_name] = 1 - sum(weights.values())

        if set(weights).issubset(set(keyvals)):
            p = sum(w * keyvals[k] for (k, w) in weights.items())
            keyvals['w_Weighted_system_pwr'] = p
            keyvals['hours_battery_Weighted'] = self.energy_full_design / p

        self.write_perf_keyval(keyvals)
        self._plog.save_results(self.resultsdir)


    def cleanup(self):
        # cleanup() is run by common_lib/test.py
        try:
            self._test_server.stop()
        except AttributeError:
            logging.debug('test_server could not be stopped in cleanup')

        if self._backlight:
            self._backlight.restore()
        if self._services:
            self._services.restore_services()

        super(power_Consumption, self).cleanup()
