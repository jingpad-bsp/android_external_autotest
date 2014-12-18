# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file contains utility functions to get and set stable versions for given
# boards.

import common
import django.core.exceptions
from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import models


# Name of the default board. For boards that don't have stable version
# explicitly set, version for the default board will be used.
DEFAULT = 'DEFAULT'

def get_all():
    """Get stable versions of all boards.

    @return: A dictionary of boards and stable versions.
    """
    return dict([(v.board, v.version)
                 for v in models.StableVersion.objects.all()])


def get_version(board=DEFAULT):
    """Get stable version for the given board.

    @param board: Name of the board, default to value `DEFAULT`.
    @return: Stable version of the given board. Return global configure value
             of CROS.stable_cros_version if stable_versinos table does not have
             entry of board DEFAULT.
    """
    try:
        return models.StableVersion.objects.get(board=board).version
    except django.core.exceptions.ObjectDoesNotExist:
        if board == DEFAULT:
            return global_config.global_config.get_config_value(
                    'CROS', 'stable_cros_version')
        else:
            return get_version(board=DEFAULT)
