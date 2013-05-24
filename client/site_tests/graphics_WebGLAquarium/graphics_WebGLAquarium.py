# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a client side WebGL aquarium test."""

import logging
import os
import threading
import time

import sampler
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import chrome


class graphics_WebGLAquarium(test.test):
    """WebGL aquarium graphics test."""
    version = 1

    def setup(self):
        tarball_path = os.path.join(self.bindir,
                                    'webgl_aquarium_static.tar.bz2')
        utils.extract_tarball_to_dir(tarball_path, self.srcdir)

    def initialize(self):
        self.test_settings = {
                1: ('setSetting0', 0),
                10: ('setSetting1', 1),
                50: ('setSetting2', 2),
                100: ('setSetting3', 3),
                250: ('setSetting4', 4),
                500: ('setSetting5', 5),
                1000: ('setSetting6', 6),
        }
        self.perf_keyval = {}
        self.flip_stats = {}
        self.active_tab = None
        self.sampler_lock = threading.Lock()
        if utils.get_board().lower() in ['daisy', 'daisy_spring']:
            # Enable ExynosSampler on Exynos platforms.  The sampler looks for
            # exynos-drm page flip states: 'wait_kds', 'rendered', 'prepared',
            # and 'flipped' in kernel debugfs.

            # Sample 3-second durtaion for every 5 seconds.
            self.kernel_sampler = sampler.ExynosSampler(period=5, duration=3)
            self.kernel_sampler.sampler_callback = self.exynos_sampler_callback
            self.kernel_sampler.output_flip_stats = (
                    self.exynos_output_flip_stats)
        else:
            # TODO: Create samplers for other platforms (e.g. x86).
            self.kernel_sampler = None

    def run_fish_test(self, browser, test_url, num_fishes):
        """Run the test with the given number of fishes.

        @param browser: The Browser object to run the test with.
        @param test_url: The URL to the aquarium test site.
        @param num_fishes: The number of fishes to run the test with.
        """
        # Create tab and load page. Set the number of fishes when page is fully
        # loaded.
        tab = browser.tabs.New()
        tab.Navigate(test_url)
        tab.Activate()
        self.active_tab = tab

        # Set the number of fishes when document finishes loading.  Also reset
        # our own FPS counter and start recording FPS and rendering time.
        utils.wait_for_value(lambda: tab.EvaluateJavaScript(
                'if (document.readyState === "complete") {'
                '  setSetting(document.getElementById("%s"), %d);'
                '  g_crosFpsCounter.reset();'
                '  true;'
                '} else {'
                '  false;'
                '}' % self.test_settings[num_fishes]),
                expected_value=True, timeout_sec=30)

        if self.kernel_sampler:
            self.kernel_sampler.start_sampling_thread()
        time.sleep(self.test_duration_secs)
        if self.kernel_sampler:
            self.kernel_sampler.stop_sampling_thread()
            self.kernel_sampler.output_flip_stats(
                    'flip_stats_%d' % num_fishes)
            self.flip_stats = {}

        # Get average FPS and rendering time, then close the tab.
        avg_fps = tab.EvaluateJavaScript('g_crosFpsCounter.getAvgFps();')
        avg_render_time = tab.EvaluateJavaScript(
                'g_crosFpsCounter.getAvgRenderTime();')
        self.perf_keyval['avg_fps_%04d_fishes' % num_fishes] = avg_fps
        self.perf_keyval['avg_render_time_%04d_fishes' % num_fishes] = (
                avg_render_time)
        logging.info('%d fish(es): Average FPS = %f, average render time = %f',
                     num_fishes, avg_fps, avg_render_time)

        # Do not close the tab when the sampler_callback is doing his work.
        with self.sampler_lock:
            tab.Close()
            self.active_tab = None

    def exynos_sampler_callback(self, sampler_obj):
        """Sampler callback function for ExynosSampler.

        @param sampler_obj: The ExynosSampler object that invokes this callback
                function.
        """
        if sampler_obj.stopped:
            return

        with self.sampler_lock:
            now = time.time()
            results = {}
            info_str = ['\nfb_id wait_kds flipped']
            for value in sampler_obj.frame_buffers.itervalues():
                results[value.fb] = {}
                for state, stats in value.states.iteritems():
                    results[value.fb][state] = (stats.avg, stats.stdev)
                info_str.append('%s: %s %s' % (
                        value.fb, results[value.fb]['wait_kds'][0],
                        results[value.fb]['flipped'][0]))
            results['avg_fps'] = self.active_tab.EvaluateJavaScript(
                    'g_crosFpsCounter.getAvgFps();')
            results['avg_render_time'] = self.active_tab.EvaluateJavaScript(
                    'g_crosFpsCounter.getAvgRenderTime();')
            self.active_tab.ExecuteJavaScript('g_crosFpsCounter.reset();')
            info_str.append('avg_fps: %s, avg_render_time: %s' %
                            (results['avg_fps'], results['avg_render_time']))
            self.flip_stats[now] = results
            logging.info('\n'.join(info_str))

    def exynos_output_flip_stats(self, file_name):
        """Pageflip statistics output function for ExynosSampler.

        @param file_name: The output file name.
        """
        # output format:
        # time fb_id avg_rendered avg_prepared avg_wait_kds avg_flipped
        # std_rendered std_prepared std_wait_kds std_flipped
        with open(file_name, 'w') as f:
            for t in sorted(self.flip_stats.keys()):
                if ('avg_fps' in self.flip_stats[t] and
                    'avg_render_time' in self.flip_stats[t]):
                    f.write('%s %s %s\n' % (
                            t, self.flip_stats[t]['avg_fps'],
                            self.flip_stats[t]['avg_render_time']))
                for fb, stats in self.flip_stats[t].iteritems():
                    if not isinstance(fb, int):
                        continue
                    f.write('%s %s ' % (t, fb))
                    f.write('%s %s %s %s ' % (stats['rendered'][0],
                                              stats['prepared'][0],
                                              stats['wait_kds'][0],
                                              stats['flipped'][0]))
                    f.write('%s %s %s %s\n' % (stats['rendered'][1],
                                               stats['prepared'][1],
                                               stats['wait_kds'][1],
                                               stats['flipped'][1]))

    def run_once(self, test_duration_secs=30,
                 test_setting_num_fishes=(1, 10, 50, 100, 250, 500, 1000)):
        """Find a brower with telemetry, and run the test.

        @param test_duration_secs: The duration in seconds to run each scenario
                for.
        @param test_setting_num_fishes: A list of the numbers of fishes to
                enable in the test.
        """
        self.test_duration_secs = test_duration_secs
        self.test_setting_num_fishes = test_setting_num_fishes

        with chrome.Chrome() as cr:
            cr.browser.SetHTTPServerDirectories(self.srcdir)
            test_url = cr.browser.http_server.UrlOf(
                os.path.join(self.srcdir, 'aquarium.html'))
            for n in self.test_setting_num_fishes:
                self.run_fish_test(cr.browser, test_url, n)

        self.write_perf_keyval(self.perf_keyval)
