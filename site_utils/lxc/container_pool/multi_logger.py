# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging


def create(name):
    """Creates a custom logger for better multithreaded logging."""
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(
            logging.Formatter('%(asctime)s [%(threadName)s] %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
