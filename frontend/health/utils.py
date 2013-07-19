# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.frontend import setup_django_readonly_environment

# Django and the models are only setup after
# the setup_django_readonly_environment module is imported.
from autotest_lib.frontend.tko import models as tko_models
from django.db import models as django_models

_TEST_PASS_STATUS = 'GOOD'

def get_last_pass_times():
    """
    Get all the tests that have passed and the time they last passed.

    @return the dict of test_name:last_finish_time pairs for tests that have
            passed.

    """
    results = tko_models.Test.objects.values('test').filter(
        status__word=_TEST_PASS_STATUS).annotate(
        last_pass=django_models.Max('started_time'))
    return {result['test']: result['last_pass'] for result in results}

