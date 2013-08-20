# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy, logging, os, pprint, re, threading, time, urllib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, httpd
from autotest_lib.client.cros.audio import audio_helper

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
<th>Card</th>
<th>Device</th>
<th>Channels</th>
<th>Format</th>
<th>Sample Rates</th>
<th>Controls</th>
</tr>
'''
_DEVICE_SECTION_END = '</table></td></tr>'
_DEVICE_SECTION_ENTRY_TMPL = '''<tr>
<td>%(name)s</td>
<td>%(list_index)d</td>
<td>%(card_index)d</td>
<td>%(device_index)d</td>
<td>%(channels)d</td>
<td>%(sample_format)s</td>
<td>%(sample_rate)s</td>
<td>%(control_names)s</td>
</tr>
'''

_DEVICE_SECTION_ENTRY_PORT_START_TMPL = '''<tr>
<td>%(name)s</td>
<td>%(index)d</td>
<td>%(channels)d</td>
<td>%(sample_format)s</td>
<td>%(sample_rate)s</td>
'''
_DEVICE_SECTION_ENTRY_PORT_END_TMPL = '''<td>%s</td>
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

_TEST_CONTROL_START = '<table><th>Test descriptions</th><th>Invoke Link</th>'
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

_INVALID_INSTRUCTIONS = '''<p>
No test exists yet for this.
'''

_GENERIC_TEST_INFO = '''<p>
<b>%(name)s</b> will be run on the <b>%(device)s</b> device.
'''

_MIXER_LIST_START = '<div class="mixer_table">'
_MIXER_LIST_END = '</div>'
_MIXER_SECTION_START  = '''<tr><td><table class="mixer_section">
<tr>
<th>Mixer Control</th>
<th>Setting</th>
</tr>
'''

_MIXER_SECTION_END = '</table></td></tr>'
_MIXER_SECTION_ENTRY_TMPL = '''<tr>
<td>%(name)s</td>
<td>%(value)s</td>
</tr>
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

_VOLUME_TEST_DETAILS2 = '''<p>
Playback will be on all channels, and run for 5 seconds.

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
    <li>16 test tones, following A# Harmonic Minor Scale, up and down.
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
<li>A 4 second sample will be recorded.
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

# Names of mixer controls
_CONTROL_MASTER = "'Master'"
_CONTROL_HEADPHONE = "'Headphone'"
_CONTROL_SPEAKER = "'Speaker'"
_CONTROL_CAPTURE = "'(Capture|MIC1)'"
_CONTROL_PCM = "'PCM'"

# Names for various test webpages.
_CONTROL_ENDPOINT = 'control'
_LIST_ENDPOINT = 'list'
_VOLUME_ENDPOINT = 'volume'
_PLAYBACK_ENDPOINT = 'playback'
_RECORD_ENDPOINT = 'record'
_TEST_ENDPOINT = 'test'

# Test names
_VOLUME_TEST = 'volume'
_TONES_TEST = 'tones'
_RECORD_TEST = 'record'


# Configuration for the test program invocation.
_TONE_LENGTH_SEC = 0.5
_TONE_DEFAULT_VOLUME = 0.2
_MIXER_DEFAULT_VOLUME = "90%"
_VOLUME_TEST_VOLUME = 90

# Tests to perform, and mixer settings to use for the tests.  'X' denotes a
# volume that will be varied by the (volume) test

_DEVICE = "HDA Intel|DAISYI2S"
_TESTS = [{'name': "Volume Test (Master)",
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_HEADPHONE, 'value': "100% on"},
                     {'name':_CONTROL_SPEAKER, 'value': "100% on"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'active': _CONTROL_MASTER,
           'test': _VOLUME_TEST},

          {'name': 'Tones Test (Master)',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': _MIXER_DEFAULT_VOLUME},
                     {'name':_CONTROL_HEADPHONE, 'value': "100% on"},
                     {'name':_CONTROL_SPEAKER, 'value': "100% on"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'test': _TONES_TEST},

          {'name': 'Volume Test (Speakers Only)',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': "100% on"},
                     {'name':_CONTROL_HEADPHONE, 'value': "0% off"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'active': _CONTROL_SPEAKER,
           'test': _VOLUME_TEST},

          {'name': 'Tones Test (Speakers Only)',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': _MIXER_DEFAULT_VOLUME},
                     {'name':_CONTROL_HEADPHONE, 'value': "0% off"},
                     {'name':_CONTROL_SPEAKER, 'value': "100% on"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'test': _TONES_TEST},

          {'name': 'Volume Test (Headphones Only)',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': "100% on"},
                     {'name':_CONTROL_SPEAKER, 'value': "0% off"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'active': _CONTROL_HEADPHONE,
           'test': _VOLUME_TEST},

          {'name': 'Tones Test (Headphones Only)',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': _MIXER_DEFAULT_VOLUME},
                     {'name':_CONTROL_SPEAKER, 'value': "0% off"},
                     {'name':_CONTROL_HEADPHONE, 'value': "100% on"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'test': _TONES_TEST},

          {'name': 'Recording Test',
           'device': _DEVICE,
           'mixer': [{'name':_CONTROL_MASTER, 'value': _MIXER_DEFAULT_VOLUME},
                     {'name':_CONTROL_SPEAKER, 'value': "100% on"},
                     {'name':_CONTROL_HEADPHONE, 'value': "100% on"},
                     {'name':_CONTROL_PCM, 'value':"100% on"}],
           'record': _CONTROL_CAPTURE,
           'test': _RECORD_TEST}
         ]

# Device regexp, adds '*' before and after device in _TESTS before comparing
_NAME_RE_TEMPLATE_ = "(.*)%s(.*)"

_USR_BIN_PATH = '/usr/bin/'

# Regexps for parsing 'aplay -l'
_CARD_RE = re.compile('card (\d+):\s(.+)\s\[(.+)\],\s+device\s(.+):.+\[(.*)\]')

# Regexps for parsing 'amixer'
_MIXER_CONTROL_RE = re.compile('Simple mixer control \'(.+)\',(\d+)')
_MIXER_CAPS_RE = re.compile('\s+Capabilities:\s+(.+)')
_MIXER_LIMITS_RE = re.compile('\s+Limits:\s*(.*) (\d+) - (\d+)')
_MIXER_CHANNELS_RE = re.compile('(.+)channels:\s(.+)')
_MIXER_CHANNEL_LIST_RE = re.compile('(.+) - (.+)')
_MIXER_DIRECTION_RE = re.compile('.*(Playback|Capture).*')

# Regexps for parsing output of alsa_caps.
_CAPS_RATES_RE = re.compile('Rates: (.*)')
_CAPS_CHANNELS_RE = re.compile('Channels: (.*)')
_CAPS_FORMATS_RE = re.compile('Formats: (.*)')

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

    def __init__(self, audio, start_volume, end_volume, card, period, control):
        """Changes the volume to end_volume over period seconds.

        Volume will be updated as max every 50ms, with a target of reaching max
        volume for the last 100ms of playback.

        Args:
            audio: An instance of the audio object.
            start_volume: An integer specifying the start volume.
            end_volume: An integer specifying the stop volume.
            card: The index of the audio card to test.
            period: The period, in seconds, over which to adjust the volume from
                    start_volume to end_volume.
            control: Adjust volume of this control.
        """
        threading.Thread.__init__(self)
        self.audio = audio
        self.start_volume = start_volume
        self.end_volume = end_volume
        self.card = card
        self.period = period
        self.control = control


    def run(self):
        delta = self.end_volume - self.start_volume
        start = time.time()
        end = start + self.period - 0.1  # Hit max volume 100ms before end.
        now = start
        last_volume = 0
        while now < end:
            elapsed = now - start
            new_volume = int(self.start_volume + delta * elapsed / self.period)
            if new_volume != last_volume:
                self.audio.do_set_volume_alsa(self.card, self.control,
                        new_volume)
                last_volume = new_volume
            time.sleep(self._WAKE_INTERVAL_SEC)
            now = time.time()
        self.audio.do_set_volume_alsa(self.card, self.control, self.end_volume)


class audiovideo_PlaybackRecordSemiAuto(cros_ui_test.UITest):
    version = 1
    preserve_srcdir = True
    crash_handling_enabled = False

    def default_tone_config(self):
        return { 'type': 'tone',
                 'frequency': 1000,
                 'tone_length_sec': _TONE_LENGTH_SEC,
                 'tone_volume': _TONE_DEFAULT_VOLUME,
                 'channels': 2,
                 'active_channel': None,
                 'alsa_device': 'default'
                 }


    def cmd(self, cmd):
        """
        Wrap a shell command with the necessary permissions.
        """
        cmd = 'su chronos -c "%s"' % cmd
        return cmd


    def setup(self):
        # build alsa_caps as well.
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make()


    def initialize(self, creds = '$default'):
        id = 0
        for test in _TESTS:
            test['id'] = id
            id = id + 1

        self._pp = pprint.PrettyPrinter()
        logging.info('Test Definitions:')
        logging.info(self._pp.pformat(_TESTS))

        self._alsa_caps_path = os.path.join(self.srcdir, 'alsa_caps')
        if not (os.path.exists(self._alsa_caps_path) and
                os.access(self._alsa_caps_path, os.X_OK)):
            raise error.TestError(
                    '%s is not an executable' % self._alsa_caps_path)

        self._playback_devices = self.enumerate_playback_devices()
        self._record_devices = self.enumerate_record_devices()
        logging.info(self._pp.pformat(self._playback_devices))
        logging.info(self._pp.pformat(self._record_devices))

        # Test state.
        self._running_test = None
        self._results = {}

        # Run test server.
        self._server_root = 'http://localhost:8000/'
        self._testServer = httpd.HTTPListener(port=8000, docroot=self.bindir)
        self._testServer.run()
        super(audiovideo_PlaybackRecordSemiAuto, self).initialize(creds)


    def cleanup(self):
        self._testServer.stop()
        super(audiovideo_PlaybackRecordSemiAuto, self).cleanup()


    def run_once(self, timeout=10000):
        self._testServer.add_url_handler(
                '/%s' % _CONTROL_ENDPOINT,
                lambda server, form, o=self: o.handle_control(server, form))
        self._testServer.add_url_handler(
                '/%s' % _LIST_ENDPOINT,
                lambda server, form, o=self: o.handle_list(server, form))
        self._testServer.add_url_handler(
                '/%s' % _TEST_ENDPOINT,
                lambda server, form, o=self: o.handle_test(server, form))

        latch = self._testServer.add_wait_url('/done')

        # Temporarily increment pyauto timeout
        pyauto_timeout_changer = self.pyauto.ActionTimeoutChanger(
            self.pyauto, timeout * 1000)
        self.pyauto.NavigateToURL(self._server_root + _CONTROL_ENDPOINT)
        del pyauto_timeout_changer

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


    def get_pass_fail_div(self, endpoint, dict):
        """Geneates HTML for a pass-fail link to finish a test case."""
        dict['result'] = 'pass'
        pass_url = '%s?%s' % (endpoint, urllib.urlencode(dict))
        dict['result'] = 'fail'
        fail_url = '%s?%s' % (endpoint, urllib.urlencode(dict))
        return _TEST_RESULT % (pass_url, fail_url)


    def handle_list(self, server, args):
        """Handles the list test endpoint.

        Prints out a list of all playback and record hardware devices found.
        """
        self.wait_for_current_test()

        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = { 'test': _LIST_ENDPOINT, 'device': 0, 'num': 0 }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_DEVICE_LIST_INSTRUCTIONS)

        # Output device summary.
        server.wfile.write(_DEVICE_LIST_START)

        server.wfile.write(_PLAYBACK_SECTION_LABEL)
        server.wfile.write(_DEVICE_SECTION_START)
        for device in self._playback_devices['info']:
            server.wfile.write(_DEVICE_SECTION_ENTRY_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_END)

        server.wfile.write(_RECORD_SECTION_LABEL)
        server.wfile.write(_DEVICE_SECTION_START)
        for device in self._record_devices['info']:
            server.wfile.write(_DEVICE_SECTION_ENTRY_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_END)

        server.wfile.write(_DEVICE_LIST_END)

        # End Page.
        server.wfile.write(_HTML_FOOTER)


    def handle_test(self, server, args):
        """Handles the generic 'test' point.

        Uses the 'num' arg as the test number to run.
        The device index is passed in the 'device' arg.
        """
        logging.info('Test configuration:')
        logging.info(args)

        found_test = None
        for test in _TESTS:
            if test['id'] == int(args['num'][0]):
                found_test = test
                break

        logging.info('-- handle_test found:')
        logging.info(self._pp.pformat(found_test))

        if found_test is None:
            return

        self.wait_for_current_test()

        device_index = int(args['device'][0])
        if found_test['test'] == _VOLUME_TEST:
            self.handle_volume_test(server, found_test, device_index)
        elif found_test['test'] == _TONES_TEST:
            self.handle_tones_test(server, found_test, device_index)
        elif found_test['test'] == _RECORD_TEST:
            self.handle_record_test(server, found_test, device_index)
        else:
            logging.error('Cannot find test %s' % (found_test['test']))
            server.wfile.write(_INVALID_INSTRUCTIONS)


    def handle_volume_test(self, server, test, device_idx):
        """Handles volume calibration test

        Performs a volume calibration test on the device.  This is separated
        from the normal playback tests as a safety.  This test should be run
        before the playback test to make sure the test volume isn't dangerous
        to either listener or equipment.
        """
        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _TEST_ENDPOINT,
                'device': device_idx,
                'num': test['id']
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_VOLUME_INSTRUCTIONS)
        server.wfile.write(_VOLUME_TEST_DETAILS2)

        self.render_test_info(server, test)

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self._running_test = threading.Thread(
                target=lambda t=test,d=device_idx: self.do_volume_test(t, d))
        self._running_test.start()


    def handle_tones_test(self, server, test, device_idx):
        """Handles test tone generation test

        Generates test tones.  Mixer should be set up before running test to
        hear if the mixer settings perform as expected.
        """
        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _TEST_ENDPOINT,
                'device': device_idx,
                'num': test['id']
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_PLAYBACK_INSTRUCTIONS)
        self.render_test_info(server, test)

        device = self.get_device_by_idx(device_idx, self._playback_devices)
        self.render_channel_test_order(server, device)

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self._running_test = threading.Thread(
                target=lambda t=test,d=device_idx: self.do_playback_test(t, d))
        self._running_test.start()


    def handle_record_test(self, server, test, device_idx):
        """Handles record and playback test

        Display the record test page, then run the test.  A short sample is
        recorded, then played back with various mixer settings.
        """
        server.wfile.write(_HTML_HEADER_TMPL % _STATIC_CSS)

        test_data = {
                'test': _TEST_ENDPOINT,
                'device': device_idx,
                'num': test['id']
                }
        server.wfile.write(
                self.get_pass_fail_div(_CONTROL_ENDPOINT, test_data))

        server.wfile.write(_RECORD_INSTRUCTIONS)
        self.render_test_info(server, test)

        # End Page.
        server.wfile.write(_HTML_FOOTER)

        self._running_test = threading.Thread(
                target=lambda t=test,d=device_idx: self.do_record_test(t, d))
        self._running_test.start()


    def expected_num_tests(self):
        """Returns the expected number of tests to have been run."""
        expected_tests = 1  # For the device list test.

        for device in self._playback_devices['info']:
            for test in _TESTS:
                regexp = re.compile(_NAME_RE_TEMPLATE_ % (test['device']))
                m = regexp.match(device['name'])
                if m is not None:
                    expected_tests = expected_tests + 1

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
            self.get_test_key(_LIST_ENDPOINT, 0, 0),
            _LIST_ENDPOINT))

        # For each playback device found, display all matching tests
        for device in self._playback_devices['info']:
            # Treat the 'device' in _TESTS as a regexp we try to match.
            for test in _TESTS:
                regexp = re.compile(_NAME_RE_TEMPLATE_ % (test['device']))
                m = regexp.match(device['name'])
                if m is not None:
                    server.wfile.write(self.get_testing_item(
                            device['list_index'],
                            test['id']))

        server.wfile.write(_TEST_CONTROL_END)

        # End Page.
        server.wfile.write(_HTML_FOOTER)


    def render_single_device_summary(self, server, device, port):
        """Output a HTML table with information on a single device"""
        server.wfile.write(_DEVICE_LIST_START)
        server.wfile.write(_DEVICE_SECTION_START)
        server.wfile.write(_DEVICE_SECTION_ENTRY_PORT_START_TMPL % device)
        server.wfile.write(_DEVICE_SECTION_ENTRY_PORT_END_TMPL % port)
        server.wfile.write(_DEVICE_SECTION_END)
        server.wfile.write(_DEVICE_LIST_END)

    def render_test_info(self, server, test):
        """Output in HTML a list of the test attributes"""
        server.wfile.write(_GENERIC_TEST_INFO % test)

        server.wfile.write(_MIXER_LIST_START)
        server.wfile.write(_MIXER_SECTION_START)
        for control in test['mixer']:
            server.wfile.write(_MIXER_SECTION_ENTRY_TMPL % control)
        server.wfile.write(_MIXER_SECTION_END)
        server.wfile.write(_MIXER_LIST_END)

        if 'active' in test:
            server.wfile.write('<p>Active Control: %s</p>' % (test['active']))
        if 'record' in test:
            server.wfile.write('<p>Record Control: %s</p>' % (test['record']))


    def render_channel_test_order(self, server, device):
        """Output HTML a table with device channel ordering info."""
        server.wfile.write('<p>Channels will be tested in this order:<ol>')
        for channel in xrange(0, device['channels']):
            if 'channel_map' in device:
                server.wfile.write('<li>%s' % device['channel_map'][channel])
            else:
                server.wfile.write('<li>%d' % channel)

        server.wfile.write('<li>All channels')
        server.wfile.write('</ol>')


    def get_result_css(self, results):
        """Color the test invocation links based on the pass/fail result."""
        stanzas = []
        for key in results.keys():
            if results[key] == 'pass':
                stanzas.append(_RESULT_PASS_CSS % key)
            elif results[key] == 'fail':
                stanzas.append(_RESULT_FAIL_CSS % key)
        return '\n'.join(stanzas)


    def get_test_key(self, test, device=None, port=None):
        """Generate a string represeting the test case."""
        return '%s-%s-%s' % (test, device, port)


    def add_results(self, args):
        """Process CGI arguments for the test result, and record it."""
        if 'test' not in args:
            return

        key = self.get_test_key(args['test'][0],
                                args['device'][0],
                                args['num'][0])
        self._results[key] = args['result'][0]


    def wait_for_current_test(self):
        """Used to prevent multiple tests from running at once."""
        if self._running_test is not None:
            self._running_test.join()


    def get_testing_item(self, device_idx, test_id):
        """Geneates HTML for a test invocation table entry."""
        device = self._playback_devices['info'][device_idx]

        args = { 'device': device_idx, 'num': test_id}
        description = '%s on %s' % (_TESTS[test_id]['name'], device['name'])
        invoke_url = '%s?%s' % (_TEST_ENDPOINT, urllib.urlencode(args))
        return _TEST_CONTROL_ITEM % (description,
                                     self.get_test_key(_TEST_ENDPOINT,
                                                       device_idx,
                                                       test_id),
                                     invoke_url)


    def get_alsa_device_caps(self, device_info, direction):
        """Get capabilites of the device.
        Sample rates, formats, and number of channels supported.

        Args:
            device_info: dictionary containing card and device index.
        """
        cmd = self._alsa_caps_path + ' hw:%u,%u ' % (device_info['card_index'],
                device_info['device_index'])
        cmd += direction.lower()
        caps_output = self.do_cmd(cmd)
        for line in caps_output.split('\n'):
            m = _CAPS_FORMATS_RE.match(line)
            if m is not None:
                device_info['sample_format'] = m.group(1)
            m = _CAPS_CHANNELS_RE.match(line)
            if m is not None:
                device_info['channels'] = int(m.group(1))
            m = _CAPS_RATES_RE.match(line)
            if m is not None:
                device_info['sample_rate'] = m.group(1)


    def parse_device_info_alsa(self, device_info_output, direction):
        """Parses the output of an "aplay -l" or "arecord -l" call."""
        device_info = { 'info' : [] }
        current_device = None
        port_parsing_mode = False
        list_index = 0
        for line in device_info_output.split('\n'):
            m = _CARD_RE.match(line)
            if m is not None:
                current_device = {}
                current_device['list_index'] = list_index
                list_index = list_index + 1
                current_device['card_index'] = int(m.group(1))
                current_device['device_index'] = int(m.group(4))
                current_device['control_names'] = []
                current_device['card'] = m.group(2)
                current_device['name'] = '%s (%s) %s' % (m.group(2),
                                                         m.group(3),
                                                         m.group(5))
                # Fake some capabilities for now,  These are filled in later
                # with info from alsa_caps.
                current_device['channels'] = 2
                current_device['sample_rate'] = 'Unknown'
                current_device['sample_format'] = 'Unknown'

                self.get_alsa_device_caps(current_device, direction)

                device_info['info'].append(current_device)
        return device_info


    def merge_controls_alsa(self, device_info, mixer_output, direction):
        """Helper function for parsing the lines from amixer output.
           Look for 'pvolume' Capabilities, and insert mixer control name
        """
        device_info['controls'] = []
        current_control = None
        for line in mixer_output.split('\n'):
            m = _MIXER_CONTROL_RE.match(line)
            if m is not None:
                if current_control is not None:
                    if direction == current_control['direction']:
                        device_info['control_names'].append(
                                current_control['name'])
                        device_info['controls'].append(current_control)
                current_control = {}
                current_control['name'] =  '\'%s\',%d' % (m.group(1),
                                                          int(m.group(2)))
                current_control['direction'] = 'Invalid'
                if re.compile('.*((?i)mic).*').match(current_control['name']):
                    current_control['direction'] = 'Capture'
            if current_control is not None:
                m = _MIXER_CAPS_RE.match(line)
                if m is not None:
                    current_control['caps'] = m.group(1)

                m = _MIXER_LIMITS_RE.match(line)
                if m is not None:
                    if _MIXER_DIRECTION_RE.match(m.group(1)):
                        current_control['direction'] = m.group(1)
                    current_control['min_volume'] = int(m.group(2))
                    current_control['max_volume'] = int(m.group(3))

                m = _MIXER_CHANNELS_RE.match(line)
                if m is not None:
                    current_control['channel_map'] = []
                    channel_list = m.group(2)
                    while (True):
                        mm = _MIXER_CHANNEL_LIST_RE.match(channel_list)
                        if mm is None:
                            current_control['channel_map'].append(channel_list)
                            break
                        else:
                            current_control['channel_map'].append(mm.group(1))
                            channel_list = mm.group(2)
                # While direction has not been decided yet, match all lines
                # in the output which might tell us the direction.
                if current_control['direction'] == 'Invalid':
                    m = _MIXER_DIRECTION_RE.match(line)
                    if m:
                        current_control['direction'] = m.group(1)

        if current_control is not None:
            if direction == current_control['direction']:
                device_info['control_names'].append(current_control['name'])
                device_info['controls'].append(current_control)


    def enumerate_playback_devices(self):
        """Queries Alsa for all available controls (mixer elements).

        Retruns:
           A dictionary with the number of devices found, and the
           parsed output of the "aplay -l" call.
        """
        list_aplay_output = self.do_cmd('aplay -l')

        device_info = self.parse_device_info_alsa(list_aplay_output, 'Playback')

        for device in device_info['info']:
            cmd = 'amixer -c %d' % (device['card_index'])
            list_amixer_output = self.do_cmd(cmd)
            self.merge_controls_alsa(device, list_amixer_output, 'Playback')
        return device_info


    def enumerate_record_devices(self):
        """Queries Alsa for all available capture elements.

        Retruns:
           A dictionary with the number of devices found, and the
           parsed output of the "arecord -l" call.
        """
        list_arecord_output = self.do_cmd('arecord -l')
        logging.info(list_arecord_output)

        device_info = self.parse_device_info_alsa(list_arecord_output,
                                                  'Capture')

        for device in device_info['info']:
            cmd = 'amixer -c %d' % (device['card_index'])
            list_amixer_input = self.do_cmd(cmd)
            self.merge_controls_alsa(device, list_amixer_input, 'Capture')
        return device_info


    def set_active_control(self, device, control_name):
        """Sets the active control, e.g. which control volume change affects

        Args:
          device: A dictionary with the parsed device information.
          control_name: The name of the control port to use.
        """

        logging.info('Setting active control to %s' % (control_name))

        for control in device['controls']:
            if re.compile(_NAME_RE_TEMPLATE_ %
                    control_name).match(control['name']):
                device['active_control'] = control
                break

    def set_control_volumes(self, device, mixer):
        """Sets all controls listed in mixer on device

        Args:
          device: Device dictionary
          mixer: mixer list from _TESTS
        """
        logging.info('Setting mixer control values on %s' % (device['name']))
        logging.info(self._pp.pformat(mixer))

        for item in mixer:
            logging.info('item in mixer:')
            logging.info(self._pp.pformat(item))
            control = self.find_control(item['name'], device)
            if control is not None:
                self.do_set_volume_alsa(device['card_index'],
                        control, item['value'])


    def do_signal_test_end(self):
        """Play 3 short 1000Hz tones to signal a test case's completion.

        Playback is done on whatever the current default device is.
        """
        config = self.default_tone_config()
        config['tone_length_sec'] = 0.25
        self.play_tone(config, 1000)
        self.play_tone(config, 1000)
        self.play_tone(config, 1000)


    def do_record_test(self, test, device_idx):
        """Runs the record and playback test using test's configuration.

        Args:
            test: An item from _TESTS
            device_idx: index of device to run test on
        """
        logging.info('-- recording test')

        device_play = self.get_device_by_idx(device_idx, self._playback_devices)
        device_rec = self.get_device_by_idx(device_idx, self._record_devices)

        if device_play is None:
            logging.error('Playback device not found')
            return
        if device_rec is None:
            logging.error('Record device not found')
            return

        # Set playback volumes.
        self.set_control_volumes(device_play, test['mixer'])

        # Set to max hardware amplification record volume.
        self.set_active_control(device_rec, test['record'])
        if not 'active_control' in device_rec:
            logging.error('No record control found')
            return

        control = device_rec['active_control']
        self.do_set_volume_alsa(device_rec['card_index'], control, "100% cap")

        # Record from each channel, then from all channels.
        num_channels = len(device_rec['active_control']['channel_map'])
        for channel in xrange(0, num_channels):
            logging.info('-- record max vol channel %s' %
               control['channel_map'][channel])
            self.record_playback_sample(device_rec, channel)

        # Try recording at max, un-amped, 50% amp, and mute volumes.
        logging.info('-- record max vol all channels')
        self.do_set_volume_alsa(device_rec['card_index'], control, "100% cap")
        self.record_playback_sample(device_rec, None)

        half_amp_volume = control['max_volume'] / 2.0

        logging.info('-- record half-amp volume all channels')
        self.do_set_volume_alsa(device_rec['card_index'], control, "%d cap" %
                (half_amp_volume))
        self.record_playback_sample(device_rec, None)

        logging.info('-- record muted all channels')

        self.do_set_volume_alsa(device_rec['card_index'], control, "100% nocap")
        self.record_playback_sample(device_rec, None)

        # Reset mic to on and max level
        self.do_set_volume_alsa(device_rec['card_index'], control, "100% cap")
        self.do_signal_test_end()


    # There is a lag between invocation of the recording process
    # and when it actually starts recording. A 4sec "duration" makes a
    # good default because it generates about 2sec worth of recording
    # when playing back the recording.
    def record_playback_sample(self, device, channel, duration=4):
        """Records a sample from the default input device and plays it back.

        Args:
            device: device info dictionary gotten from
                    enumerate_record devices()
            channel: Which channel to record from. "None" to specify all.
            duration: How long to record in seconds.
                      (Duration > 3sec to be discernable)
        """
        # Record a sample.
        try:
            tmpfile = os.path.join(self.tmpdir, os.tmpnam())

            # Set the volume to max on given channel, zero for all others
            record_args = ''
            if channel is not None:
                vol_arg = ''
                num_channels = len(device['active_control']['channel_map'])
                for chan in xrange(0, num_channels):
                    if chan == channel:
                        chan_vol = "100%"
                    else:
                        chan_vol = "0%"
                    if len(vol_arg):
                        vol_arg = "%s," % (vol_arg)
                    vol_arg = "%s%s" % (vol_arg, chan_vol)
                self.do_set_volume_alsa(device['card_index'],
                        device['active_control'], vol_arg)

            cmd_rec = 'arecord -d %f -f cd %s' % (duration, tmpfile)

            logging.info('running %s' % self.cmd(cmd_rec))

            # Record the sample
            signal_config = self.default_tone_config()
            signal_config['tone_length_sec'] = 0.25
            self.play_tone(signal_config, 1000)  # Signal record start.
            logging.info('Record now (%fs)' % duration)
            utils.system(self.cmd(cmd_rec))

            # Playback the sample.
            self.play_tone(signal_config, 500)  # Signal playback start.
            cmd_play = 'aplay %s' % (tmpfile)
            logging.info('Playing back sample')
            utils.system(self.cmd(cmd_play))

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

    def find_control(self, name, device):
        """Return the control from the controls list for device

        Args:
            name: name of control to find
            device: device from devices dictionary
        """
        for control in device['controls']:
            if name in control['name']:
                return control
        return None


    def get_device_by_idx(self, index, devices):
        """Return the device in the devices dictionary with the given index

        Args:
            index: index of device
            devices: dictionary of devices from enumerate_playback_devices()
        """
        for device in devices['info']:
            if device['list_index'] == index:
                return device
        return None


    def do_volume_test(self, test, device_idx):
        """Runs a volume calibration test on the given device.

        Args:
            test: An item from _TESTS
            device_idx: index of device to run test on
        """
        logging.info('-- volume calibration all channels')

        device = self.get_device_by_idx(device_idx, self._playback_devices)

        if device is not None:
            self.set_control_volumes(device, test['mixer'])
            if 'active' in test:
                self.set_active_control(device, test['active'])
            self.do_volume_calibration_test(device)


    def do_playback_test(self, test, device_idx):
        """Runs test tones the given device using test's configuration.

        Args:
            test: An item from _TESTS
            device_idx: index of device to run test on
        """
        logging.info('-- tones playback test')

        device = self.get_device_by_idx(device_idx, self._playback_devices)
        alsa_device = ('plughw:%d,%d' % (device['card_index'],
                                         device['device_index']))

        if device is not None:
            self.set_control_volumes(device, test['mixer'])
            for channel in xrange(0, device['channels']):
                logging.info('-- playback channel %d' % (channel))
                self.do_tone_test(alsa_device, channel)
                self.do_scale_test(alsa_device, channel)

            # Run it once for all channels enabled.
            logging.info('-- playback all channels')
            self.do_tone_test(alsa_device)
            self.do_scale_test(alsa_device)
            self.do_signal_test_end()


    def get_test_volume(self, device):
        """Attempts to guess at a good playback test volume.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
        """
        # TODO(ajwong): What is a good test volume? 80% of max default is
        # pretty arbitrary.
        test_volume = (device['active_control']['max_volume'] *
            _VOLUME_TEST_VOLUME / 100)
        return test_volume


    def do_volume_calibration_test(self, device):
        """Play 1000Hz test tone for 5 seconds, slowly raising the volume.

        The volume will be a increased from 0 until the value of
        get_test_volume() over the 5-second period.

        Args:
            device: device info dictionary gotten from
                    enumerate_playback_devices()
        """

        if not 'active_control' in device:
            logging.error('No active control set')
            return

        config = self.default_tone_config()
        config['tone_length_sec'] = 5

        # Silence and un-mute the active control.
        self.do_set_volume_alsa(device['card_index'],
                device['active_control'], 0)
        self.do_set_mute_alsa(device['card_index'], device['active_control'], 0)

        # TODO(ajwong): What is a good test volume? 50% of max default is
        # pretty arbitrary.
        test_volume = self.get_test_volume(device)

        # Set the alsa device to use to play the tones.
        alsa_device = ('plughw:%d,%d' % (device['card_index'],
                                         device['device_index']))
        config['alsa_device'] = alsa_device

        tone_thread = ToneThread(self, config)

        volume_change_thread = VolumeChangeThread(self, 0, test_volume,
                                                  device['card_index'],
                                                  config['tone_length_sec'],
                                                  device['active_control'])
        volume_change_thread.start()
        tone_thread.start()
        tone_thread.join()
        volume_change_thread.join()

        self.do_signal_test_end()


    def do_cmd(self, command):
        """Helper function for invoking a command."""
        logging.info(command)
        return utils.system_output(self.cmd(command), retain_output=True)


    def do_set_volume_alsa(self, card, control, new_volume):
        """Helper function for invoking 'amixer sset' command.

        Args: card: audio card number to set
              control: control structure from device dictionary
              new_volume: Either percentage, e.g. "50%" or actual value in range
                          of control's min_volume to max_volume
        """
        if 'volume' in control['caps']:
            result = self.do_cmd('amixer -c %d sset %s %s' %
                    (card, control['name'], new_volume))


    def do_set_mute_alsa(self, card, control, mute):
        """Helper function for invoking 'amixer sset' command.

        Args: card: audio card number to set
              control: control structure from device dictionary
              new_mute: Either 1 for mute or 0 for unmuted
        """
        if 'pswitch' in control['caps']:
            enabled = ['on', 'off']
            result = self.do_cmd('amixer -c %d sset %s %s' %
                    (card, control['name'], enabled[mute]))


    def play_tone(self, base_config, frequency):
        """Convenience function to play a test tone at a given frequency.

        Args:
            base_config: base tone configuration
            frequency: new frequency to play tone at
        """
        config = copy.copy(base_config)
        config['frequency'] = frequency
        self.run_test_tones(config)


    def do_tone_test(self, alsa_device, active_channel=None):
        """Plays 10 test tones from 30Hz to 20000Hz.

        Args:
            active_channel: integer identifying the channel to output test on.
                            If None, all channels are active.
        """
        config = self.default_tone_config()
        config['active_channel'] = active_channel
        config['alsa_device'] = alsa_device;

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


    def do_scale_test(self, alsa_device, active_channel=None):
        """Plays the A# harmonic minor scale test on.

        Args:
            active_channel: integer identifying the channel to output test on.
                            If None, all channels are active.
        """
        config = self.default_tone_config()
        config['active_channel'] = active_channel
        config['alsa_device'] = alsa_device;
        config['type'] = 'scale'
        self.run_test_tones(config)


    def run_test_tones(self, args):
        """Runs the tone generator executable.

        Args:
            args: A hash listing the parameters for test_tones.
                  Required keys:
                    exec - Executable to run
                    type - 'scale' or 'tone'
                    frequency - float with frequency in Hz.
                    tone_length_sec - float with length of test tone in secs.
                    tone_volume - float with volume to do tone (0 to 1.0)
                    channels - number of channels in output device.

                  Optional keys:
                    active_channel: integer to select channel for playback.
                                    None means playback on all channels.
        """
        args['exec'] = audio_helper.TEST_TONES_PATH

        if not 'tone_end_volume' in args:
            args['tone_end_volume'] = args['tone_volume']

        cmd = ('%(exec)s '
               '-t %(type)s -h %(frequency)f -l %(tone_length_sec)f '
               '-c %(channels)d -s %(tone_volume)f '
               '-e %(tone_end_volume)f' % args)
        if args['active_channel'] is not None:
            cmd += ' -a %s' % args['active_channel']
        if args['alsa_device'] is not None:
            cmd += ' -d %s' % args['alsa_device']
        if args['type'] == 'tone':
            logging.info('[tone %dHz]' % args['frequency'])
        elif args['type'] == 'scale':
            logging.info('[A# harmonic minor scale]')
        utils.system(cmd)
