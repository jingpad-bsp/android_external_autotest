# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Relocate the large string templates to one place.

# Common constants.
AUTOTEST_ARCHIVE = 'gs://chromeos-autotest-results'
AUTOTEST_PATH = '/usr/local/autotest'
AUTOTEST_SERVER = 'http://cautotest'
AUTOTEST_USER = 'chromeos-test'

BVT_TAG = 'bvt'
KERNELTEST_TAG = 'kerneltest'

EMAIL_TRIGGER_COMPLETED = 'completed'
EMAIL_TRIGGER_FAILED = 'failed'
EMAIL_TRIGGER_CHANGED = 'result_changed'

DASHBOARD_MAIN = 'run_generate.py'

EMAILS_SUMMARY_FILE = 'emails.html'
TEST_LANDING_FILE = 'index.html'
TEST_TABLE_FILE = 'table_index.html'
TEST_WATERFALL_FILE = 'waterfall_index.html'
TIMING_SUMMARY_FILE = 'bvt_timing.html'
KERNEL_TABLE_FILE = 'kernel_index.html'
KERNEL_WATERFALL_FILE = 'waterfall_kernel.html'
TEST_DETAILS_FILE = 'details.html'
TESTS_STATUS_FILE = 'tests_%s.html'
PERFORMANCE_REGRESSED_EMAIL = 'performance_regressed.html'
BUILD_PERFORMANCE_FILE = 'build_performance.html'
PLOT_FILE = 'index.html'
PERF_INDEX_FILE = 'perf_index.html'
PERF_BUILDS_FILE = 'perf_builds.html'

LOCAL_TMP_DIR = './dashcache'
EMAIL_DIR = 'emails'
JOB_RESULT_DIR = 'job_results'
PERFORMANCE_DIR = 'performance'
TEST_EMAIL_DIR = 'test'

BUILDTIME_PREFIX = '.tmp_buildtime_'
TEST_CHECKED_PREFIX = '.tmp_emailed_'
ALERT_CHECKED_PREFIX = '.tmp_alerted_'

PREPROCESSED_TAG = '__pp__'

LAST_N_JOBS_LIMIT = 500  # Scan only the last N jobs for relevant results.
SUMMARY_TABLE_ROW_LIMIT = 50  # display max of the latest n test builds.

# Email constants.
EMAIL_BUILDS_TO_CHECK = 2
EMAIL_TESTS_PER_ROW = 4

# Buildbot URLS.
BUILDBOT_URLS = {
    'x86-generic-full':
      ('http://buildbot.jail.google.com/i/chromiumos/%sbuilders/'
       'x86 generic full/builds'),
    'x86-alex-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-alex canary/builds'),
    'x86-alex-r16':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-alex full release-R16-1193.B/builds'),
    'x86-alex-r15':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-alex full release-1011.B/builds'),
    'x86-alex-r14':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-alex release 0.14.811.B/builds'),
    'x86-mario-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-mario canary/builds'),
    'x86-mario-r16':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-mario full release-R16-1193.B/builds'),
    'x86-mario-r15':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-mario full release-1011.B/builds'),
    'x86-mario-r14':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-mario release 0.14.811.B/builds'),
    'stumpy-r16':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'stumpy canary/builds'),
    'stumpy-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'stumpy canary/builds'),
    'tegra2-seaboard-r16':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'tegra2_seaboard canary/builds'),
    'tegra2-seaboard-cosine-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'tegra2_seaboard-tangent canary/builds'),
    'tegra2-kaen-r16':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'tegra2_kaen canary/builds'),
    'tegra2-kaen-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'tegra2_kaen canary/builds'),
    'x86-zgb-r17':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-zgb canary/builds'),
    'x86-zgb-r16':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-zgb full release-R16-1193.B/builds'),
    'x86-zgb-r15':
      ('http://buildbot.jail.google.com/i/chromiumos.release/%sbuilders/'
       'x86-zgb full release-1011.B/builds'),
    'x86-zgb-r14':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-zgb release 0.14.811.B/builds'),
    'x86-zgb-r13':
      ('http://chromeos-botmaster.mtv.corp.google.com:8026/%sbuilders/'
       'x86-zgb release 0.13.587.B/builds')}

# Image URLs.
IMAGE_URLS = {
    'x86-generic-full':
      ('https://sandbox.google.com/storage/chromeos-image-archive/'
       'x86-generic-full/'),
    'x86-alex-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-alex/'),
    'x86-alex-r16':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-alex/'),
    'x86-alex-r15':
      ('https://sandbox.google.com/storage/chromeos-releases/beta-channel/'
       'x86-alex/'),
    'x86-alex-r14':
      ('https://sandbox.google.com/storage/chromeos-releases/stable-channel/'
       'x86-alex/'),
    'x86-mario-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-mario/'),
    'x86-mario-r16':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-mario/'),
    'x86-mario-r15':
      ('https://sandbox.google.com/storage/chromeos-releases/beta-channel/'
       'x86-mario/'),
    'x86-mario-r14':
      ('https://sandbox.google.com/storage/chromeos-releases/stable-channel/'
       'x86-mario/'),
    'stumpy-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'stumpy/'),
    'tegra2-seaboard-cosine-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'tegra2-seaboard/'),
    'tegra2-kaen-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'tegra2-kaen/'),
    'x86-zgb-r17':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-zgb/'),
    'x86-zgb-r16':
      ('https://sandbox.google.com/storage/chromeos-releases/dev-channel/'
       'x86-zgb/'),
    'x86-zgb-r15':
      ('https://sandbox.google.com/storage/chromeos-releases/beta-channel/'
       'x86-zgb/'),
    'x86-zgb-r14':
      ('https://sandbox.google.com/storage/chromeos-releases/stable-channel/'
       'x86-zgb/')}

GSUTIL_GET_CMD = 'gsutil cat '
WGET_CMD = 'wget --timeout=30 --tries=1 --no-proxy -qO- '

# SUMMARY PAGE templates

UNKNOWN_TIME_STR = 'None'

# EMAIL templates.

STATUS_PASSED = 'success'
STATUS_FAILED = 'failure'

EMAIL_TESTS_SUBJECT = (
    'Autotest %(status)s in %(categories)s on %(board)s (%(build)s)')

EMAIL_ALERT_DELTA_TABLE_SKELETON = """
<table bgcolor="#e5e5c0" cellspacing="1"
cellpadding="2" style="margin-right:200px;">
<tr>
  <td colspan=5><center><h3>DELTA Summary for %(test_name)s<h3></center></td>
</tr>
<tr>
  <td><center>Key</center></td>
  <td><center>Delta Latest<br>Build</center></td>
  <td><center>Delta Average<br>Prev Builds</center></td>
  <td><center>Latest<br>Build</center></td>
  <td><center>Average<br>Prev Builds</center></td>
</tr>
%(body)s
</table>
<br>
"""

EMAIL_ALERT_DELTA_TABLE_ROW = """
<tr>
  <td><center><b><tt>%(key)s</tt></b></center></td>
  <td><center><b><tt>%(pp_latest)s</tt></b></center></td>
  <td><center><b><tt>%(pp_average)s</tt></b></center></td>
  <td><center><b><tt>%(latest)s</tt></b></center></td>
  <td><center><b><tt>%(average)s</tt></b></center></td>
</tr>
"""

# PLOT PAGE templates
PLOT_ANCHOR = """
<hr><center><a name="%(test_name)s">%(test_name)s</a><center><br>"""

# URL base for email links.
EMAIL_URL_BASE = 'http://goto/chromeos-dash/'

# Tree closing utility and message format.
TREE_CLOSER = '/usr/local/autotest/utils/set_tree_status.py'
TREE_CLOSER_MSG = (
    'Tree is closed (Automatic tree closure due to failing tests. %s)')

CHANGELOG_URL = 'http://chromeos-images/diff/report?from=%s&to=%s'
CHROME_CHANGELOG_URL = (
    'http://omahaproxy.appspot.com/changelog?old_version=%s&new_version=%s')
