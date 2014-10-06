#!/bin/bash
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Author: truty@google.com (Mike Truty)
#
# This script for building dash and copying resulting files.

declare -r SCRIPT_DIR="$(cd $(dirname $0); pwd)"

declare -r EXEC_BASE=$(dirname "$0")
declare -r RESULTS_BASE="/usr/local/autotest/results/dashboard"

declare -r RESULTS_SERVER="cautotest.corp.google.com"
declare -r ROLE_ACCOUNT="chromeos-test"

set -e

function create_copy_dash() {
  local result_base=$1
  local result_parent=$(dirname ${result_base})
  local job_limit=$2
  local extra_options=$3

  ${EXEC_BASE}/run_generate.py \
    --config-file=${EXEC_BASE}/dash_config.json \
    -d ${result_base} \
    -j ${job_limit} \
    ${extra_options} &> /dev/null
}

if [[ $1 != "dashboard" && $1 != "email" ]]; then
  echo "Usage: `basename $0` [dashboard | email]"
  exit $E_BADARGS
fi

if [[ $1 == "dashboard" ]]; then
  # Create and copy regular dash.
  create_copy_dash ${RESULTS_BASE} 10000 "-t -p"
  # Generate alerts.
  create_copy_dash ${RESULTS_BASE} 3000 "-a"
elif [[ $1 == "email" ]]; then
  # Create and copy regular dash.
  create_copy_dash ${RESULTS_BASE} 1500 "-m"
fi
