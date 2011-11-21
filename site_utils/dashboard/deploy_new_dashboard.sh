#!/bin/bash
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Author: truty@google.com (Mike Truty)
#
# This script for updating dashboard source.

declare -r SCRIPT_DIR="$(cd $(dirname $0); pwd)"

declare -r DASH_BASE="/usr/local/autotest/results/dashboard"
declare -r EXEC_BASE="/usr/local/autotest/utils/dashboard"
declare -r SOURCE_BASE="/home/$USER/autotest-tools"
declare -r TEMPLATE_BASE="/usr/local/autotest/frontend/templates"

set -e

cp -r ${SOURCE_BASE}/dashboard/* ${EXEC_BASE}
cp -r ${EXEC_BASE}/templates/* ${TEMPLATE_BASE}
cp ${SOURCE_BASE}/cron/chromeos_test_config.json ${EXEC_BASE}
${EXEC_BASE}/table_from_test_dash_json.py -d ${DASH_BASE}
