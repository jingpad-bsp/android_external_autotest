# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy, logging, os, pprint, re, threading, time, urllib

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_httpd, site_ui, utils

# HTML templates.
_STATIC_CSS ='''
form {
  margin: 0;
}
td {
    border-width: 1px;
    border-style: solid;
}
th {
    border-width: 1px;
    border-style: solid;
}
.control {
    background-color: yellow;
}
.completion {
    background-color: #999999;
    border-width: 1px;
    border-style: dashed;
}
'''

_RESULT_PASS_CSS ='''
td#%s {
    background-color: green;
}
'''

_RESULT_FAIL_CSS ='''
td#%s {
    background-color: red;
}
'''

_HTML_HEADER_TMPL = '''<html>
<head><title>AudioVideo_PlaybackRecordSemiAuto Test</title>
<style type="text/css"> <!--
%s
-->
</style>
</head>
<body>'''
_HTML_FOOTER = '''
</body>
</html>'''

_DEVICE_LIST_INSTRUCTIONS = '''<p>
This is the device list test.  There should be an entry for each hardware
device on the system.  The test is a pass if every expected hardware device
is listed.
'''

_DEVICE_LIST_START = '<div class="device_table">'
_DEVICE_LIST_END = '</div>'

_PLAYBACK_SECTION_LABEL = '''Playback Devices'''
_RECORD_SECTION_LABEL = '''Capture Devices'''

_DEVICE_SECTION_START = '''<tr><td><table class="device_section">
<tr>
<th>Name</th>
<th>Index</th>
<th>Channels</th>
<th>Is Hardware</th>
<th>Default Format</th>
<th>Default Sample Rate</th>
<th>Ports</th>
</tr>
'''
_DEVICE_SECTION_END = '</table></td></tr>'
_DEVICE_SECTION_ENTRY_TMPL = '''<tr>
<td>%(name)s</td>
<td>%(index)d</td>
<td>%(channels)d</td>
<td>%(is_hardware)d</td>
<td>%(sample_format)s</td>
<td>%(sample_rate)s</td>
<td>%(ports)s</td>
</tr>
'''

_DEVICE_LIST_TEST = '''
<tr><td><table> <tr>
<td>Device List Looks Correct?</td>
<td class="action" id="summary"><a href="?test=summary&result=pass">pass</a>
<a href="?test=summary&result=fail">fail</a>
</td>
</tr></table></td></tr>
'''

_TEST_CONTROL_START = '<table><th>Test description</th><th>Invoke Link</th>'
_TEST_CONTROL_END = '</table>'

_TEST_CONTROL_ITEM = '''
<tr><td>%s</td><td id="%s" class="control"><a href="%s">invoke</a></td></tr>
'''

_TEST_RESULT = '''<h1 class="completion">
Test Result: <a href="%s">PASS</a> <a href="%s">FAIL</a>
</h1>
'''
_TEST_COMPLETE = '''<h1 class="completion">
End Test: <a href="done">DONE</a></h1>
'''

_VOLUME_INSTRUCTIONS = '''<p>
This is a volume calibration test.  For the hardware device listed below, a
1000Hz test tone will be played, starting from 0 volume, ramping up until the
volume to be used by the rest of the tests on this device.

<b>IF THIS CAUSES DISCOMFORT TO THE LISTENER, DO NOT CONTINUE WITH THE OTHER
PLAYBACK TESTS</b>
'''

_VOLUME_TEST_DETAILS = '''<p>
Playback will be on %(channels)d channels, and run for 5 seconds.

<p>
After the whole test is completed, three quick 1000Hz pulses will be played.
'''

_PLAYBACK_INSTRUCTIONS = '''<p>
This is a playback test.  For the hardware device listed below, the following
tests sequence will be done once for evey channel configuration listed 
at the end of the page:
<ol>
    <ol>
    <li>10 tone test for frequences (HZ): 30, 50, 100, 250, 500, 1000, 5000,
        10000, 15000, 20000
    <li>14 test tones, following A# Harmonic Minor Scale, up and down.
    </ol>
</ol>

<p>
After the whole test is completed, three quick 1000Hz pulses will be played.

<p>
The test is a pass if every tone can be heard.
'''

_RECORD_INSTRUCTIONS = '''<p>
This is a record test.  For the hardware device listed below, a record
test will be done.  A sample will be recorded from the given device
and port, and then played back on the first port of the first playback
device listed.

<p>
Different amplification settings for the mic will be used.  Playback
volume will be set at the default test volume used during the tone tests.
The following tests will be done.

<p>
At maximum hardware input amplificaiton, for each channel of the device:
<ol>
<li>A short 1000Hz tone will be played to signal the start of recording.
<li>A 500Hz tone will be played to signal the start of playback.
<li>A 1.5 second sample will be recorded.
</ol>

<p>
This test sequence will also be repeated with all channels enabled with
the mic input amplification set at:
    <ol>
    <li>Maximum hardware amplificaiton.
    <li>50% hardware amplificaiton.
    <li>input muted.
    </ol>

<p>
After the whole test is completed, three quick 1000Hz pulses will be played.

<p>
The test is a pass if the recording can be heard during playback with
reasonable clarity and volume for each non-muted setting.  The last test,
with the input muted, should yield nothing at playback.
'''

# Names for various test webpages.
_CONTROL_ENDPOINT = 'control'
_LIST_ENDPOINT = 'list'
_VOLUME_ENDPOINT = 'volume'
_PLAYBACK_ENDPOINT = 'playback'
_RECORD_ENDPOINT = 'record'


# Configuration for the test program invocation.
_TONE_LENGTH_SEC = 0.3

_PACMD_PATH = '/usr/bin/pacmd'
_PACAT_PATH = '/usr/bin/pacat'

# Regexps for parsing device stanzas.
_COUNT_RE = re.compile('>>> (\d+) (source|sink)\(s\) available.')
_STANZA_START_RE = re.compile('  (\*| ) index: (\d+)')
_NAME_RE = re.compile('\tname:\s+<(.+)>')
_FLAGS_RE = re.compile('\tflags:\s+(.+)')
_MAX_VOLUME_RE = re.compile('\tvolume steps:\s+(\d+)')
_BASE_VOLUME_RE = re.compile('\tbase volume:\s+(\d+)%')
_SAMPLE_SPEC_RE = re.compile('\tsample spec:\s+(\S+) (\d+)ch (\d+)Hz')
_CHANNEL_MAP_RE = re.compile('\tchannel map:\s+(.+)')
_TOP_LEVEL_RE = re.compile('\t\S')
_PORTS_RE = re.compile('\tports:')
_PORT_SPEC_RE = re.compile('\t\t(\S+): .* \(priority \d+\)')


class ToneThread(threading.Thread):
    """Wraps the running of test_tones in a thread."""
    def __init__(self, audio, config):
        threading.Thread.__init__(self)
        self.audio = audio
        self.config = config

    def run(self):
        self.audio.run_test_tones(self.config)


class VolumeChangeThread(threading.Thread):
    _WAKE_INTERVAL_SEC = 0.02

    def __init__(self, audio, type, index, start_volume, end_volume, period):
        """Changes the volume to end_volume over period seconds.

        Volume will be updated as max every 50ms, with a target of reaching max
        volume for the last 100ms of playback.

        Args:
            audio: An instance of the audio object.
            type: Either "source" or "sink".
            index: The index value of the specific source or sink to use.
            start_volume: An integer specifying the start volume.
            end_volume: An integer specifying the stop volume.
            period: The period, in seconds, over which to adjust the volume from
                    start_volume to end_volume.
        """
        threading.Thread.__init__(self)
        self.audio = audio
        self.type = type
        self.index = index
        self.start_volume = start_volume
        self.end_volume = end_volume
        self.period = period


    def run(self):
        delta = self.end_volume - self.start_volume
        start = time.time()
        end = start + self.period - 0.1  # Hit max volume 100ms before end.
        now = start
        while now < end:
            elapsed = now - start
            new_volume = int(self.start_volume + delta * elapsed / self.period)
            self.audio.do_set_volume(self.type, self.index, new_volume)
            time.sleep(self._WAKE_INTERVAL_SEC)
            now = time.time()
        self.audio.do_set_volume(self.type, self.index, self.end_volume)


class audiovideo_PlaybackRecordSemiAuto(test.test):
    version = 1
    preserve_srcdir = True
    crash_handling_enabled = False

    def default_tone_config(self):
        return { 'type': 'tone',
                 'frequency': 1000,
                 'tone_length_sec': 0.5,
                 'channels': 2,
                 'active_channel': None
                 }


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make')


    def initialize(self):
        self._playback_devices = self.enumerate_playback_devices()
        self._record_devices = self.enumerate_record_devices()
        self._test_tones_path = os.path.join(self.srcdir, "test_tones")
        if not (os.path.exists(self._test_tones_path) and
                os.access(self._test_tones_path, os.X_OK)):
            raise error.TestError(
                    '%s is not an executable' % self._test_tones_path)
        self._pp = pprint.PrettyPrinter()
        logging.info(self._pp.pformat(self._playback_devices))
        logging.info(self._pp.pformat(self._record_devices))

        # Test state.
        self._running_test = None
        self._results = {}

        # Run test server.
        self._server_root = 'http://localhost:8000/'
        self._testServer = site_httpd.HTTPListener(port=8000,
                                                   docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        self._testServer.stop()


    def run_once(self, timeout=10000):
        self._testServer.add_url_handler(
                '/%s' % _CONTROL_ENDPOINT,
                lambda server, form, o=self: o.handle_control(server, form))
        self._testServer.add_url_handler(
                '/%s' % _LIST_ENDPOINT,
                lambda server, form, o=self: o.handle_list(server, form))
        self._testServer.add_url_handler(
                '/%s' % _VOLUME_ENDPOINT,
                lambda server, form, o=self: o.handle_volume(server, form))
        self._testServer.add_url_handler(
                '/%s' % _PLAYBACK_ENDPOINT,
                lambda server, form, o=self: o.handle_playback(server, form))
        self._testServer.add_url_handler(
                '/%s' % _RECORD_ENDPOINT,
                lambda server, form, o=self: o.handle_record(server, form))

        latch = self._testServer.add_wait_url('/done')
        try:
            session = site_ui.ChromeSession(
                    self._server_root + _CONTROL_ENDPOINT)
            logging.debug('Chrome session started.')

            latch.wait(timeout)
            if not latch.is_set():
                raise error.TestFail('Timeout.')

            expected_num_tests = self.expected_num_tests()
            finished_tests = len(self._results)
            results = self._pp.pformat(self._results)
            if finished_tests != expected_num_tests:
                raise error.TestFail(
                        'Expected %d test results, found %d. Results %s' % (
                            expected_num_tests, finished_tests, results))

            logging.info('result = ' + results)
            failed_tests = []
            for key, value in self._results.items():
                # TODO(ajwong):  YOU NEED TO MAKE THIS ITERATION CORRECT.
                if value != 'pass':
                    failed_tests.append((key, value))

            if len(failed_tests):
                raise error.TestFail(
                        'User indicated test failure(s). Failed: %s' %
                        self._pp.pformat(failed_tests))
        finally:
            session.close()


    def get_pass_fail_div(self, endpoint, dict):
        """Geneates HTML for a pass-fail link to finish a test case."""
        dict['result'] = 'pass'
        pass_url = '%s?%s' % (endpoint, urllib.urlencode(dict))
        dict['result'] = 'fail'
        fail_url = '%s?%s' % (endpoint, urllib.urlencode(dict))
        return _TEST_RESULT % (pass_url, fail_url)


    def handle_list(self, server, args):
        """Handles the list test endpoint.

        Prints out a list of all hardware devices found by pulseaudio.
        """
        self.wait_for_current_test()

        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = { 'test': _LIST_ENDPOINT, 'device': 0, 'port': 0 }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_DEVICE_LIST_INSTRUCTIONS)

        # Output device summary.
        server.wfile.write(_DEVICE_LIST_START)

        server.wfile.write(_PLAYBACK_SECTION_LABEL)
        server.wfile.write(_DEVICE_SECTION_START)
        for device in self._playback_devices['info']:
            if device['is_hardware']:
                server.wfile.write(_DEVICE_SECTION_ENTRY_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_END)

        server.wfile.write(_RECORD_SECTION_LABEL)
        server.wfile.write(_DEVICE_SECTION_START)
        for device in self._record_devices['info']:
            if device['is_hardware']:
                server.wfile.write(_DEVICE_SECTION_ENTRY_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_END)

        server.wfile.write(_DEVICE_LIST_END)

        # End Page.
        server.wfile.write(_HTML_FOOTER)


    def handle_volume(self, server, args):
        """Handles the volume test point.

        Performs a volume calibration test on the device.  This is separated
        from the normal playback tests as a safety.  This test should be run
        before the playback test to make sure the test volume isn't dangerous
        to either listener or equipment.
        """
        self.wait_for_current_test()

        (device_num, port_num, device, port) = self.get_device_info(args, 
                self._playback_devices)

        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _VOLUME_ENDPOINT,
                'device': device_num,
                'port': port_num
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_VOLUME_INSTRUCTIONS)

        self.render_single_device_summary(server, device)

        server.wfile.write(_VOLUME_TEST_DETAILS % device)
        if device.has_key('channel_map'):
            server.wfile.write('<p>Channels are: %s' %
                    self._pp.pformat(device['channel_map']))

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self._running_test = threading.Thread(
                target=lambda d=device,p=port: self.do_volume_test(d,p))
        self._running_test.start()


    def handle_playback(self, server, args):
        """Handles the playback test endpoint.

        Performs a playback test on the given device and port.
        """
        self.wait_for_current_test()

        (device_num, port_num, device, port) = self.get_device_info(args, 
                self._playback_devices)

        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _PLAYBACK_ENDPOINT,
                'device': device_num,
                'port': port_num
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_PLAYBACK_INSTRUCTIONS)

        self.render_single_device_summary(server, device)
        self.render_channel_test_order(server, device, port)

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self.wait_for_current_test()
        self._running_test = threading.Thread(
                target=lambda d=device,p=port: self.do_playback_test(d,p))
        self._running_test.start()


    def handle_record(self, server, args):
        """Handles the playback test endpoint.

        Performs a record test on the given device and port.
        """
        self.wait_for_current_test()

        (device_num, port_num, device, port) = self.get_device_info(args, 
                self._record_devices)

        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _RECORD_ENDPOINT,
                'device': device_num,
                'port': port_num
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_RECORD_INSTRUCTIONS)

        self.render_single_device_summary(server, device)
        self.render_channel_test_order(server, device, port)

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self.wait_for_current_test()
        self._running_test = threading.Thread(
                target=lambda d=device,p=port: self.do_record_test(d,p))
        self._running_test.start()


    def expected_num_tests(self):
        """Returns the expected number of tests to have been run."""
        expected_tests = 1  # For the device list test.

        # There is a volume calibration test, and a test tone test for
        # each port on a playback device.
        for device in self._playback_devices['info']:
            if device['is_hardware']:
                num_ports = len(device['ports'])
                if num_ports > 0:
                    expected_tests += 2 * num_ports
                else:
                    expected_tests += 2

        # There is a one record/playback test per record device.
        for device in self._record_devices['info']:
            if device['is_hardware']:
                num_ports = len(device['ports'])
                if num_ports > 0:
                    expected_tests += num_ports
                else:
                    expected_tests += 1
        return expected_tests


    def handle_control(self, server, args):
        """Handles GET request to the test control page."""
        self.add_results(args)

        css = '%s%s' % (_STATIC_CSS, self.get_result_css(self._results))

        server.wfile.write(_HTML_HEADER_TMPL % css)

        server.wfile.write(_TEST_COMPLETE)

        # Output list of tests tests.
        server.wfile.write(_TEST_CONTROL_START)

        server.wfile.write(_TEST_CONTROL_ITEM % (
            'Device List',
            self.get_test_key(_LIST_ENDPOINT),
            _LIST_ENDPOINT))

        for device_num in xrange(0, len(self._playback_devices['info'])):
            device = self._playback_devices['info'][device_num]
            if device['is_hardware']:
                if len(device['ports']) > 0:
                    for port_num in xrange(0, len(device['ports'])):
                        server.wfile.write(
                                self.get_volume_item(device_num, port_num))
                        server.wfile.write(
                                self.get_playback_item(device_num, port_num))
                else:
                    server.wfile.write(self.get_volume_item(device_num))
                    server.wfile.write(self.get_playback_item(device_num))

        for device_num in xrange(0, len(self._record_devices['info'])):
            device = self._record_devices['info'][device_num]
            if device['is_hardware']:
                if len(device['ports']) > 0:
                    for port_num in xrange(0, len(device['ports'])):
                        server.wfile.write(
                                self.get_record_item(device_num, port_num))
                else:
                    server.wfile.write(self.get_record_item(device_num))
        server.wfile.write(_TEST_CONTROL_END)

        # End Page.
        server.wfile.write(_HTML_FOOTER)


    def render_single_device_summary(self, server, device):
        """Output a HTML table with information on a single device"""
        server.wfile.write(_DEVICE_LIST_START)
        server.wfile.write(_DEVICE_SECTION_START)
        server.wfile.write(_DEVICE_SECTION_ENTRY_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_END)
        server.wfile.write(_DEVICE_LIST_END)


    def render_channel_test_order(self, server, device, port):
        """Output HTML a table with device channel ordering info."""
        if port != None:
            server.wfile.write('<p>Active port on device: %s' % port)
        else:
            server.wfile.write('<p>Use default (only) port.')

        server.wfile.write('<p>Channels will be tested in this order:<ol>')
        for channel in xrange(0, device['channels']):
            if device.has_key('channel_map'):
                server.wfile.write('<li>%s' % device['channel_map'][channel])
            else:
                server.wfile.write('<li>%d' % channel)

        server.wfile.write('<li>All channels')
        server.wfile.write('</ol>')


    def get_device_info(self, args, devices):
        """Translate CGI parameters into a tuple of values.

        Extracts the device, and port arugments from the the args dictionary.
        Those are the device_num, and port_num indexes.  These indexes are
        used to get information from the devices dictionary.  The extracted
        values are returned in a 4-tuple.

        If port_nume = -1, then port_info is None.

        Returns:
            (device_num, port_num, device_info, port_info)
        """
        device_num = int(args['device'][0])
        port_num = int(args['port'][0])
        device = devices['info'][device_num]
        port = None
        if port_num >= 0:
            port = device['ports'][port_num]
        return (device_num, port_num, device, port)


    def get_result_css(self, results):
        """Color the test invocation links based on the pass/fail result."""
        stanzas = []
        for key in results.keys():
            if results[key] == 'pass':
                stanzas.append(_RESULT_PASS_CSS % key)
            elif results[key] == 'fail':
                stanzas.append(_RESULT_FAIL_CSS % key)
        return '\n'.join(stanzas)


    def get_test_key(self, test, device=0, port=0):
        """Generate a string represeting the test case."""
        return '%s-%d-%d' % (test, device, port)


    def add_results(self, args):
        """Process CGI arguments for the test result, and record it."""
        if 'test' not in args:
            return

        key = self.get_test_key(args['test'][0],
                                int(args['device'][0]),
                                int(args['port'][0]))
        self._results[key] = args['result'][0]


    def wait_for_current_test(self):
        """Used to prevent multiple tests from running at once."""
        if self._running_test is not None:
            self._running_test.join()


    def get_volume_item(self, device_num, port_num=None):
        """Geneates HTML for a volume test invocation table entry."""
        device = self._playback_devices['info'][device_num]
        return self.get_test_item(_VOLUME_ENDPOINT, device, device_num,
                                  port_num)


    def get_playback_item(self, device_num, port_num=None):
        """Geneates HTML for a playback test invocation table entry."""
        device = self._playback_devices['info'][device_num]
        return self.get_test_item(_PLAYBACK_ENDPOINT, device, device_num,
                                  port_num)


    def get_record_item(self, device_num, port_num=None):
        """Geneates HTML for a record test invocation table entry."""
        device = self._record_devices['info'][device_num]
        return self.get_test_item(_RECORD_ENDPOINT, device, device_num,
                                  port_num)


    def get_test_item(self, endpoint, device, device_num, port_num=None):
        """Helper function to create test invokation table entries"""
        args = { 'device': device_num, 'port': port_num }
        if port_num is not None:
            description = '%s on %s, port %s' % (
                    endpoint, device['name'], device['ports'][port_num])
        else:
            description = 'endpoint on %s, only port' % (
                    endpoint, device['name'])
        invoke_url = '%s?%s' % (endpoint, urllib.urlencode(args))
        return _TEST_CONTROL_ITEM % (description,
                                     self.get_test_key(endpoint, device_num,
                                                       port_num),
                                     invoke_url)


    def add_port(self, port_list, line):
        """Helper function for parsing the the port field."""
        m = _PORT_SPEC_RE.match(line)
        if m is not None:
            port_list.append(m.group(1))


    def merge_sinkinfo_line(self, current_sink, line):
        """Helper function for parsing the lines in a sink description."""
        m = _NAME_RE.match(line)
        if m is not None:
            current_sink['name'] = m.group(1)

        m = _FLAGS_RE.match(line)
        if m is not None:
            flags = m.group(1)
            current_sink['is_hardware'] = flags.find('HARDWARE') != -1
            current_sink['can_mute'] = flags.find('HW_MUTE_CTRL') != -1

        m = _MAX_VOLUME_RE.match(line)
        if m is not None:
            current_sink['max_volume'] = int(m.group(1))

        m = _BASE_VOLUME_RE.match(line)
        if m is not None:
            current_sink['base_volume_percent'] = int(m.group(1))

        m = _SAMPLE_SPEC_RE.match(line)
        if m is not None:
            current_sink['sample_format'] = m.group(1)
            current_sink['channels'] = int(m.group(2))
            current_sink['sample_rate'] = int(m.group(3))

        m = _CHANNEL_MAP_RE.match(line)
        if m is not None:
            channel_map = []
            for channel in m.group(1).split(','):
                channel_map.append(channel)
            current_sink['channel_map'] = channel_map


    def parse_device_info(self, device_info_output):
        """Parses the output of a pacmd list-sources or list-sinks call."""
        device_info = { 'info' : [] }
        current_device = None
        port_parsing_mode = False
        for line in device_info_output.split('\n'):
            # Leave port_parsing_mode if we find a top-level attribute.
            if port_parsing_mode and _TOP_LEVEL_RE.match(line) is not None:
                port_parsing_mode = False

            # Grab the number of devices.
            m = _COUNT_RE.match(line)
            if m is not None:
                device_info['num_devices'] = int(m.group(1))

            # Parse the device stanza.
            m = _STANZA_START_RE.match(line)
            if m is not None:
                current_device = {}
                current_device['index'] = int(m.group(2))
                current_device['ports'] = []
                device_info['info'].append(current_device)

            if current_device is not None:
                # Enter port_parsing_mode if we find the ports line.
                if _PORTS_RE.match(line) is not None:
                    port_parsing_mode = True
                elif port_parsing_mode:
                    self.add_port(current_device['ports'], line)
                else:
                    self.merge_sinkinfo_line(current_device, line)
        return device_info


    def enumerate_playback_devices(self):
        """Queries pulseaudio for all available sinks.

        Retruns:
           A dictionary with the number of devices found, and the
           parsed output of the pacmd call.
        """
        list_sinks_output = self.do_pacmd('list-sinks')
        device_info = self.parse_device_info(list_sinks_output)
        if device_info['num_devices'] != len(device_info['info']): 
            raise error.TestError('Expected %d devices, parsed %d' %
                    (device_info['num_devices'], len(device_info['info'])))
        return device_info


    def enumerate_record_devices(self):
        """Queries pulseaudio for all available sources.

        Retruns:
           A dictionary with the number of devices found, and the
           parsed output of the pacmd call.
        """
        list_sources_output = self.do_pacmd('list-sources')
        device_info = self.parse_device_info(list_sources_output)
        if device_info['num_devices'] != len(device_info['info']): 
            raise error.TestError('Expected %d devices, parsed %d' %
                    (device_info['num_devices'], len(device_info['info'])))
        return device_info


    def set_default_device_and_port(self, type, device, port):
        """Sets the default source or sink for Pulseaudio.

        Args:
          type: Either 'sink' or 'source'
          device: A dictionary with the parsed device information.
          port: The name of the device port to use. Use None for the default.
        """
        self.do_pacmd('set-default-%s %d' % (type, device['index']))
        logging.info(
            '* Testing device %d (%s)' % (device['index'], device['name']))

        if port is not None:
            self.do_pacmd('set-%s-port %d %s' % (type, device['index'], port))
            logging.info('-- setting port %s' % port)


    def do_signal_test_end(self):
        """Play 3 short 1000Hz tones to signal a test case's completion.

        Playback is done on whatever the current default device is.
        """
        config = self.default_tone_config()
        config['tone_length_sec'] = 0.3
        self.play_tone(config, 1000)
        self.play_tone(config, 1000)
        self.play_tone(config, 1000)


    def do_record_test(self, device, port):
        """Performs a record test for the given device and port.

        This sets the default playback device is set to whatever device
        is returned first in enumerate_playback_devices().  The playback
        device is set to use its first port, unmuted, and set to the
        test_volume.

        For each channel on the given device and port, a sample is recorded
        and played-back at max source volume. Then once again with all
        channel enabled.

        Next, a sample is taken at base volume (no amplification) if
        that is available, and played back.

        This is followed by a sample at 1/2 amplifcation, and again with
        the record device muted.

        Args:
            device: device info dictionary gotten from
                    enumerate_record devices()
            port: String with the name of the port to use on the device.
                  Can be None if the device does not have multiple ports.
        """
        # Configure the playback device to something normal.
        playback_device = self._playback_devices['info'][0]
        playback_volume = self.get_test_volume(playback_device)
        playback_port = None
        if len(playback_device['ports']):
            playback_port = playback_device['ports'][0]
        self.set_default_device_and_port('sink', playback_device,
                                         playback_port)
        self.do_set_mute('sink', playback_device['index'], False)
        self.do_set_volume('sink', playback_device['index'], playback_volume)

        # Set record device.
        self.set_default_device_and_port('source', device, port)

        # Set to max hardware amplification volume.
        self.do_set_volume('source', device['index'], device['max_volume'])
        self.do_set_mute('source', device['index'], False)

        # Record from each channel, then from all channels.
        for channel in xrange(0, device['channels']):
            logging.info('-- record max vol channel %s' %
                device['channel_map'][channel])
            self.record_playback_sample(device, channel)

        # Try recording at max, un-amped, 50% amp, and mute volumes.
        logging.info('-- record max vol all channels')
        self.record_playback_sample(device, None)

        # If there's no base_volume_percent, then guess that
        # half-amplication is just 1/2 the max_volume.
        half_amp_volume = device['max_volume'] / 2.0
        if device.has_key('base_volume_percent'):
            base_volume = (device['max_volume'] *
                           device['base_volume_percent'] / 100.0)
            half_amp_volume = (base_volume + 
                               (device['max_volume'] - base_volume) / 2)
            logging.info('-- record unamplified all channels')
            self.do_set_volume('source', device['index'], base_volume)
            self.record_playback_sample(device, None)
        else:
            logging.info('[Driver does to export unamplified volume level. '
                         'Skipping test.]')

        logging.info('-- record half-amp volume all channels')
        self.do_set_volume('source', device['index'], half_amp_volume)
        self.record_playback_sample(device, None)

        logging.info('-- record muted all channels')
        if device['can_mute']:
            self.do_set_mute('source', device['index'], True)
            self.do_set_volume('source', device['index'], device['max_volume'])
        else:
            logging.info('[No hardware mute. Setting volume to 0.]')
            self.do_set_volume('source', device['index'], 0)
        self.record_playback_sample(device, None)

        self.do_signal_test_end()


    def record_playback_sample(self, device, channel, duration=1.5):
        """Records a sample from the default input device and plays it back.

        Args:
            device: device info dictionary gotten from
                    enumerate_record devices()
            channel: Which channel to record from. "None" to specify all.
            duration: How long to record in seconds.
        """
        # Record a sample.
        try:
            tmpfile = os.path.join(self.tmpdir, os.tmpnam())
            record_args = ''
            if channel is not None:
                record_args = ('--channels 1 --channel-map %s' %
                        device['channel_map'][channel])
            cmd = '%s -r %s %s' % (_PACAT_PATH, record_args, tmpfile)
            logging.info('running %s' % cmd)

            signal_config = self.default_tone_config()
            signal_config['tone_length_sec'] = 0.3
            self.play_tone(signal_config, 1000)  # Signal record start.
            logging.info('Record now (%fs)' % duration)
            job = utils.BgJob(cmd)
            time.sleep(duration)
            utils.nuke_subprocess(job.sp)

            # Job should be dead already, so join with a very short timeout.
            utils.join_bg_jobs([job], timeout=1)
            result = job.result
            if result.stdout or result.stderr:
                raise error.CmdError(
                    cmd, result,
                    'stdout: %s\nstderr: %s' % (result.stdout, result.stderr))

            # Playback the sample.
            self.play_tone(signal_config, 500)  # Signal playback start.
            cmd = '%s -p %s %s' % (_PACAT_PATH, record_args, tmpfile)
            logging.info('Playing back sample')
            utils.system(cmd)

            # TODO(ajwong): Try analyzing the sample using sox stats.
            # Example command:
            #
            #   sox -c $channel -r $rate -e $format -b $bit $tmpfile -n stat
            #
            # Then look at the "RMS amplitude" in the output and make sure
            # it's above some sane level.
            #
            # Optionally, we can denoise it first with something like.
            #
            #   sox $tmpfile -n trim 0 1 noiseprof | 
            #     sox $tmpfile reduced-$tmpfile.wav noisered
            #
            # To try and make sure we aren't picking up bad nose. Then run
            # the stats on the filtered file.
        finally:
            if os.path.isfile(tmpfile):
                os.unlink(tmpfile)


    def do_volume_test(self, device, port):
        """Runs a volume calibration test on the given device.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
            port: String with the name of the port to use on the device.
                  Can be None if the device does not have multiple ports.
        """
        self.set_default_device_and_port('sink', device, port)
        logging.info('-- volume calibration all channels')
        self.do_volume_calibration_test(device)


    def do_playback_test(self, device, port):
        """Runs the full set test tones tests on the given device.

        It does a sequence of tone test, followed by a scale test for each
        channel individually, then again for all channels.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
            port: String with the name of the port to use on the device.
                  Can be None if the device does not have multiple ports.
        """
        self.set_default_device_and_port('sink', device, port)

        # TODO(ajwong): chord test sounds terrible. fix & readd.
        for channel in xrange(0, device['channels']):
            logging.info('-- playback channel %s' %
                         device['channel_map'][channel])
            self.do_tone_test(device, channel)
            self.do_scale_test(device, channel)

        # Run it once for all channels enabled.
        logging.info('-- playback all channels')
        self.do_tone_test(device)
        self.do_scale_test(device)

        self.do_signal_test_end()


    def get_test_volume(self, device):
        """Attempts to guess at a good playback test volume.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
        """
        # TODO(ajwong): What is a good test volume? 50% of max default is
        # pretty arbitrary.
        test_volume = device['max_volume'] / 2.0
        if device.has_key('base_volume_percent'):
            test_volume *= device['base_volume_percent'] / 100.0 
        return test_volume


    def do_volume_calibration_test(self, device):
        """Play 1000Hz test tone for 5 seconds, slowly raising the volume.

        The volume will be a increased from 0 until the value of
        get_test_volume() over the 5-second period.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
        """
        config = self.default_tone_config()
        config['tone_length_sec'] = 5

        # Silence the sink.
        self.do_set_volume('sink', device['index'], 0)

        # TODO(ajwong): What is a good test volume? 50% of max default is
        # pretty arbitrary.
        test_volume = self.get_test_volume(device)

        tone_thread = ToneThread(self, config)
        volume_change_thread = VolumeChangeThread(self, 'sink',
                                                  device['index'],
                                                  0, test_volume,
                                                  config['tone_length_sec'])
        volume_change_thread.start()
        tone_thread.start()
        tone_thread.join()
        volume_change_thread.join()

        self.do_signal_test_end()


    def do_pacmd(self, command):
        """Helper function for invoking pacmd."""
        cmd = 'echo %s | %s' % (command, _PACMD_PATH)
        return utils.system_output(cmd, retain_output=True)


    def do_set_volume(self, type, index, new_volume):
        """Sets the volume for the device at index.

        Args:
            type: 'source' or 'sink'
            index: integer index of the pulse audio source or sink.
            new_volume: integer volume to set the new device to.
        """
        self.do_pacmd('set-%s-volume %d %d' % (type, index, new_volume))


    def do_set_mute(self, type, index, should_mute):
        """Mutes the device at index.
        Args:
            type: 'source' or 'sink'
            index: integer index of the pulse audio source or sink.
            should_mute: boolean saying if the device should be muted.
        """
        if should_mute:
            mute_val = 1
        else:
            mute_val = 0
        self.do_pacmd('set-%s-mute %d %d' % (type, index, mute_val))


    def play_tone(self, base_config, frequency):
        """Convenience function to play a test tone at a given frequency.

        Args:
            type: 'source' or 'sink'
            index: integer index of the pulse audio source or sink.
            new_volume: integer volume to set the new device to.
        """
        config = copy.copy(base_config)
        config['frequency'] = frequency
        self.run_test_tones(config)


    def do_tone_test(self, device, active_channel=None):
        """Plays 10 test tones from 30Hz to 20000Hz.

        Args:
            device: device info dictionary, gotten from
                    enumerate_playback_devices()
            active_channel: integer identifying the channel to output test on.
                            If None, all channels are active.
        """
        config = self.default_tone_config()
        config['active_channel'] = active_channel

        # Play the low-tones.
        self.play_tone(config, 30)
        self.play_tone(config, 50)
        self.play_tone(config, 100)

        # Play the mid-tones
        self.play_tone(config, 250)
        self.play_tone(config, 500)
        self.play_tone(config, 1000)

        # Play the high-tones
        self.play_tone(config, 5000)
        self.play_tone(config, 10000)
        self.play_tone(config, 15000)
        self.play_tone(config, 20000)


    def do_scale_test(self, device, active_channel=None):
        """Plays the A# harmonic minor scale test on.

        Args:
            device: device info description, gotten from
                    enumerate_playback_devices()
            active_channel: integer identifying the channel to output test on.
                            If None, all channels are active.
        """
        config = self.default_tone_config()
        config['active_channel'] = active_channel
        config['type'] = 'scale'
        self.run_test_tones(config)


    def do_chord_test(self):
        """Starts 4 threads to play 4 test tones in parallel."""
        config = self.default_tone_config()
        config['frequency'] = 466.16
        tonic = ToneThread(self, config)

        config = self.default_tone_config()
        config['frequency'] = 554.37
        mediant = ToneThread(self, config)

        config = self.default_tone_config()
        config['frequency'] = 698.46
        dominant = ToneThread(self, config)

        config = self.default_tone_config()
        config['frequency'] = 932.33
        supertonic = ToneThread(self, config)

        tonic.start()
        mediant.start()
        dominant.start()
        supertonic.start()

        tonic.join()
        mediant.join()
        dominant.join()
        supertonic.join()


    def run_test_tones(self, args):
        """Runs the tone generator executable.

        Args:
            args: A hash listing the parameters for test_tones.
                  Required keys:
                    exec - Executable to run
                    type - 'scale' or 'tone'
                    frequency - float with frequency in Hz.
                    tone_length_sec - float with length of test tone in secs.
                    channels - number of channels in output device.

                  Optional keys:
                    active_channel: integer to select channel for playback.
                                    None means playback on all channels.
        """
        args['exec'] = self._test_tones_path
        cmd = ('%(exec)s '
               '-t %(type)s -h %(frequency)f -l %(tone_length_sec)f '
               '-c %(channels)d' % args)
        if args['active_channel'] is not None:
            cmd += ' -a %s' % args['active_channel']
        if args['type'] == 'tone':
            logging.info('[tone %dHz]' % args['frequency'])
        elif args['type'] == 'scale':
            logging.info('[A# harmonic minor scale]')
        utils.system(cmd)
