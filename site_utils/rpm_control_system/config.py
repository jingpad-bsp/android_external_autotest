# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

import ConfigParser

rpm_config = ConfigParser.SafeConfigParser()

GLOBAL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'rpm_config.ini')
global_config_exists = os.path.exists(GLOBAL_CONFIG_FILE)
SHADOW_CONFIG_FILE = "/etc/rpm/rpm_config.ini"
shadow_config_exists = os.path.exists(SHADOW_CONFIG_FILE)

if global_config_exists:
    rpm_config.read(GLOBAL_CONFIG_FILE)
if shadow_config_exists:
    rpm_config.read(SHADOW_CONFIG_FILE)

# Hide the internals
del global_config_exists
del shadow_config_exists
