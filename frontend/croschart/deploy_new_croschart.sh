#!/bin/bash
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Author: truty@google.com (Mike Truty)
#
# This script for updating croschart source.

if [[ $# -ne 1 && $# -ne 2 ]]
then
  echo "Missing source_dir parameter."
  echo "Usage: `basename $0` croschart_source_dir [nosync]"
  exit 1
fi

declare -r SCRIPT_DIR="$(cd $(dirname $0); pwd)"
declare -r CROSCHART_SRC_DIR=$1
declare -r NOSYNC=$2

set -e

if [ "$NOSYNC" != "nosync" ]
then
  echo 'Syncing source...'
  pushd ${CROSCHART_SRC_DIR} > /dev/null
  repo sync .
  popd
fi
echo 'Updating croschart dir...'
rsync -rt ${CROSCHART_SRC_DIR}/ ${SCRIPT_DIR}/
find ${SCRIPT_DIR} -path ${SCRIPT_DIR}/.cache -prune -o \( -type d -exec chmod 755 {} \; \)
find ${SCRIPT_DIR} -path ${SCRIPT_DIR}/.cache -prune -o \( -type f -exec chmod a+r {} \; \)
chmod 770 $(basename $0)
sudo apache2ctl restart
echo 'Done.'
