# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for tracking & reporting a suite run."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging.config


def setup_logging():
    """Setup the logging for skylab suite."""
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {'format': '%(asctime)s %(levelname)-5s| %(message)s'},
        },
        'handlers': {
            'screen': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['screen'],
        },
        'disable_existing_loggers': False,
    })
