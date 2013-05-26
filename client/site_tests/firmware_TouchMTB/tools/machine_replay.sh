#!/bin/sh

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script describes how to replay the raw data and generate new logs.

PROG=$0

# THIS_SCRIPT_PATH is typically as follows
#   /usr/local/autotest/tests/firmware_TouchMTB/tools/machine_replay.sh
THIS_SCRIPT_PATH=`realpath $0`

# PROJ_PATH would be
#   /usr/local/autotest/tests/firmware_TouchMTB
TOOLS_SUBDIR="tools"
PROJ_PATH=${THIS_SCRIPT_PATH%/${TOOLS_SUBDIR}/$(basename $PROG)}

# Source the local common script.
. "${PROJ_PATH}/${TOOLS_SUBDIR}/firmware_common.sh" || exit 1

# Read command flags
. /usr/share/misc/shflags
DEFINE_string board_path '' 'the unit test path of the board' 'b'

FLAGS_HELP="USAGE: $PROG [flags]"

FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"
set -e

# Check if the board path has been specified.
if [ -z $FLAGS_board_path ]; then
  die "
    Should specify the unitest path of the board with the option '"-b"'. E.g.,
    (cr) $ tools/machine_replay.sh -b tests/logs/lumpy \n"
fi


# Make an empty directory to hold the unit test files.
TMP_LOG_ROOT="/tmp/touch_firmware_test"
make_empty_dir "$TMP_LOG_ROOT"

# Copy the unit test logs to the directory just created.
cp -r ${PROJ_PATH}/${FLAGS_board_path}/* "$TMP_LOG_ROOT"


# Replay the logs on the machine.
cd $PROJ_PATH
export DISPLAY=:0
export XAUTHORITY=/home/chronos/.Xauthority
for round_dir in "$TMP_LOG_ROOT"/*; do
  if [ -d $round_dir -a ! -L $round_dir ]; then
    OPTIONS="-m complete --skip_html -i 3 --replay $round_dir" python main.py
  fi
done
