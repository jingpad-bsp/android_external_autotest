# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common file shared by test_push of autotest and skylab.

autotest: site_utils/test_push.py
skylab: venv/skylab_staging/test_push.py
"""

# Dictionary of test results keyed by test name regular expression.
EXPECTED_TEST_RESULTS = {'^SERVER_JOB$':                 'GOOD',
                         # This is related to dummy_Fail/control.dependency.
                         'dummy_Fail.dependency$':       'TEST_NA',
                         'login_LoginSuccess.*':         'GOOD',
                         'provision_AutoUpdate.double':  'GOOD',
                         'dummy_Pass.*':                 'GOOD',
                         'dummy_Fail.Fail$':             'FAIL',
                         'dummy_Fail.RetryFail$':        'FAIL',
                         'dummy_Fail.RetrySuccess':      'GOOD',
                         'dummy_Fail.Error$':            'ERROR',
                         'dummy_Fail.Warn$':             'WARN',
                         'dummy_Fail.NAError$':          'TEST_NA',
                         'dummy_Fail.Crash$':            'GOOD',
                         'autotest_SyncCount$':          'GOOD',
                         }

EXPECTED_TEST_RESULTS_DUMMY = {'^SERVER_JOB$':       'GOOD',
                               'dummy_Pass.*':       'GOOD',
                               'dummy_Fail.Fail':    'FAIL',
                               'dummy_Fail.Warn':    'WARN',
                               'dummy_Fail.Crash':   'GOOD',
                               'dummy_Fail.Error':   'ERROR',
                               'dummy_Fail.NAError': 'TEST_NA',}

EXPECTED_TEST_RESULTS_POWERWASH = {'platform_Powerwash': 'GOOD',
                                   'SERVER_JOB':         'GOOD'}
