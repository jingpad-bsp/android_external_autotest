#!/bin/sh

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Read command flags
. /usr/share/misc/shflags
DEFINE_string "log_root_dir" "" "the log root directory" "d"
DEFINE_string "metrics" "" "display the summary metrics" "m"
DEFINE_boolean "individual" false \
               "calculate statistics for every individual round" "i"

PROG=$0
FLAGS_HELP="USAGE: $PROG [flags]"

FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"
set -e

PROJ="firmware_TouchMTB"
if [ -n "$FLAGS_log_root_dir" ]; then
  LOG_ROOT="$FLAGS_log_root_dir"
else
  LOG_ROOT="/var/tmp"
fi
TEST_DIR="${LOG_ROOT}/touch_firmware_test"
SUMMARY_ROOT="${LOG_ROOT}/summary"
SUMMARY_BASE_DIR="summary_`date -u +%Y%m%d_%H%M%S`"
SUMMARY_DIR="${SUMMARY_ROOT}/$SUMMARY_BASE_DIR"
SUMMARY_FILE="${SUMMARY_DIR}/${SUMMARY_BASE_DIR}.txt"
SUMMARY_TARBALL="${SUMMARY_BASE_DIR}.tbz2"
SUMMARY_MODULE="firmware_summary.py"

# Print an error message and exit.
die() {
  echo "$@"
  exit 1
}

# Make sure that this script is invoked in a chromebook machine.
if ! grep -q -i CHROMEOS_RELEASE /etc/lsb-release 2>/dev/null; then
  die "Error: the script '$0' should be executed in a chromebook."
fi

# Make sure that the script is located in the correct directory.
SCRIPT_DIR=$(dirname $(readlink -f $0))
SCRIPT_BASE_DIR=$(echo "$SCRIPT_DIR" | awk -F/ '{print $NF}')
if [ "$SCRIPT_BASE_DIR" != "$PROJ" ]; then
  die "Error: the script '$0' should be located under $PROJ"
fi

# Make sure that TEST_DIR only contains the desired directories.
echo "The following directories in $TEST_DIR will be included in your summary."
ls "$TEST_DIR" --hide=latest
read -p "Is this correct (y/n)?" response
if [ "$response" != "y" ]; then
  echo "You typed: $response"
  die "Please remove those undesired directories from $TEST_DIR"
fi

# Create a summary directory.
mkdir -p "$SUMMARY_DIR"

# Copy all .html and .log files in the test directory to the summary directory.
find "$TEST_DIR" \( -name \*.log -o -name \*.html \) \
  -exec cp -t "$SUMMARY_DIR" {} \;

# Run firmware_summary module to derive the summary report.
display_metrics=`[ "$FLAGS_metrics" = "" ] \
                 && echo "" || echo "-m $FLAGS_metrics"`
[ ${FLAGS_individual} -eq ${FLAGS_TRUE} ] && individual_flag="--individual" \
                                          || individual_flag=""
python "${SCRIPT_DIR}/$SUMMARY_MODULE" $display_metrics $individual_flag \
       -d "$SUMMARY_DIR" > "$SUMMARY_FILE"

# Create a tarball for the summary files.
cd $SUMMARY_ROOT
tar -jcf "$SUMMARY_TARBALL" "$SUMMARY_BASE_DIR" 2>/dev/null
echo "Summary report file: $SUMMARY_FILE"
echo "Summary tarball: ${SUMMARY_ROOT}/$SUMMARY_TARBALL"
